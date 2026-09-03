#!/usr/bin/env python3
"""One AG preview pane, discovered from the live window list.

xfce4-terminal tabs share Grok's process id. Never use PID to decide what
is Grok vs AG. Grok's pane title is not 'AG-job…'. AG preview titles start
with 'AG-job'. If that pane already exists, reuse it — do not open another.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import time

TITLE = "AG-job"
STATE_PATH = os.path.expanduser("~/.config/bridge/agy_cli/preview.json")
PREVIEW_LOG = os.path.expanduser("~/.config/bridge/agy_cli/preview.log")
JOBS = os.path.expanduser("~/.config/bridge/agy_cli/jobs")


def _env():
    env = os.environ.copy()
    env["DISPLAY"] = env.get("DISPLAY") or ":0.0"
    return env


def grok_pids() -> set[int]:
    """Process tree of grok-ide — used only so we never kill Grok's process."""
    pids: set[int] = set()
    try:
        out = subprocess.check_output(["pgrep", "-af", "grok"], text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        out = ""
    for line in out.splitlines():
        if "pgrep" in line:
            continue
        try:
            pids.add(int(line.split(None, 1)[0]))
        except ValueError:
            pass
    pid = os.getpid()
    for _ in range(32):
        pids.add(pid)
        try:
            with open(f"/proc/{pid}/stat") as f:
                st = f.read()
            rpar = st.rfind(")")
            ppid = int(st[rpar + 2 :].split()[1])
        except Exception:
            break
        if ppid <= 1:
            break
        pid = ppid
        pids.add(pid)
    return pids


def list_windows() -> list[tuple[str, int, str]]:
    """(wid, pid, title) from wmctrl."""
    try:
        out = subprocess.check_output(["wmctrl", "-lp"], text=True, env=_env(), stderr=subprocess.DEVNULL)
    except Exception:
        return []
    found = []
    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        wid, pid_s, title = parts[0], parts[2], parts[4]
        try:
            pid = int(pid_s)
        except ValueError:
            pid = 0
        found.append((wid, pid, title))
    return found


def is_preview_title(title: str) -> bool:
    t = (title or "").strip()
    if t == "AG" or t.startswith("AG "):
        return False
    return t == TITLE or t.startswith("AG-job") or t.startswith("AG CLI")


def is_grok_title(title: str) -> bool:
    t = (title or "").strip()
    return t == "AG" or t.startswith("Waiting for response") or "Grok" in t or "grok" in t


def existing_preview() -> dict | None:
    """The AG preview pane that is already on screen, if any."""
    for wid, pid, title in list_windows():
        if is_preview_title(title) and not is_grok_title(title):
            log = PREVIEW_LOG
            bits = title.split()
            if len(bits) >= 2:
                prefix = bits[-1]
                matches = glob.glob(os.path.join(JOBS, prefix + "*", "job.log"))
                if matches:
                    log = matches[0]
            return {"wid": wid, "pid": pid, "title": title, "log": log}
    return None


def preview_open() -> bool:
    """Return True if an AG preview pane is currently open on screen."""
    return existing_preview() is not None


def append_preview(text: str, log_path: str | None = None) -> None:
    paths = [PREVIEW_LOG]
    if log_path and log_path not in paths:
        paths.append(log_path)
    extra = existing_preview()
    if extra and extra.get("log") and extra["log"] not in paths:
        paths.append(extra["log"])
    for path in paths:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as f:
            f.write(text)
            if not text.endswith("\n"):
                f.write("\n")
            f.flush()


def close_wid(wid: str, pid: int, title: str) -> str:
    if is_grok_title(title):
        return "skipped-grok"
    if pid in grok_pids() and not is_preview_title(title):
        return "skipped-grok"
    subprocess.run(
        ["wmctrl", "-i", "-c", wid],
        env=_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return "closed-tab"


def close_if_success(kind: str, preview_pid: int | None = None) -> str:
    return "kept"


def ensure_preview(log_path: str, job_id: str, new_session: bool = False) -> tuple[str, int | None]:
    if os.environ.get("AGY_PREVIEW", "1") in ("0", "false", "no"):
        return "headless", None

    already = existing_preview()
    append_preview(f"\n======== JOB {job_id} log={log_path} ========\n", log_path)

    if already and not new_session:
        st = {"wid": already["wid"], "pid": already["pid"], "title": already["title"], "job_id": job_id, "log": already["log"]}
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(st, f, indent=2)
            f.write("\n")
        os.replace(tmp, STATE_PATH)
        return "reused", already.get("pid")

    if already and new_session:
        close_wid(already["wid"], already["pid"], already["title"])
        time.sleep(0.2)

    if not shutil.which("xfce4-terminal"):
        return "no-gui", None

    env = _env()
    tail_cmd = (
        "echo 'AG job preview (one window). Closing it does not kill AG.'; "
        f"echo; tail -n +1 -F {PREVIEW_LOG}"
    )
    proc = subprocess.Popen(
        [
            "xfce4-terminal",
            "--disable-server",
            f"--title={TITLE}",
            "--geometry=110x36+180+60",
            "-e",
            f"bash -lc {json.dumps(tail_cmd)}",
        ],
        env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.2)
    # If xfce still attached a tab to Grok, existing_preview will see it.
    now = existing_preview()
    pid = (now or {}).get("pid") or proc.pid
    st = {"wid": (now or {}).get("wid"), "pid": pid, "title": (now or {}).get("title") or TITLE, "job_id": job_id, "log": PREVIEW_LOG}
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=2)
        f.write("\n")
    os.replace(tmp, STATE_PATH)
    return ("opened", pid)


def reopen_preview(job_id: str | None = None, log_path: str | None = None) -> tuple[str, int | None]:
    """Opens one preview pane if missing; reuses if present."""
    if not log_path and job_id:
        p = os.path.join(JOBS, job_id, "job.log")
        if os.path.isfile(p):
            log_path = p
    log_path = log_path or PREVIEW_LOG
    return ensure_preview(log_path, job_id or "latest", new_session=False)

