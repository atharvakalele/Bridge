#!/usr/bin/env python3
"""Create a job, detach the supervisor, open a preview terminal. Return immediately."""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runner import BLOCKED, DEFAULT_MODEL, DEFAULT_TIMEOUT, _now
from sessions import forget, get_conversation
from windows import ensure_preview, preview_open


def write_json(path: str, obj: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


# job_supervisor JOBS constant — keep in sync
JOBS = os.path.expanduser("~/.config/bridge/agy_cli/jobs")
SUPERVISOR = os.path.expanduser("~/.config/bridge/agy_cli/job_supervisor.py")
QUEUE_FILE = os.path.expanduser("~/.config/bridge/agy_cli/queue.json")


def queue_push(job_id: str) -> None:
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    with open(QUEUE_FILE, "a+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.seek(0)
            content = f.read().strip()
            queue = json.loads(content) if content else []
            if not isinstance(queue, list):
                queue = []
            if job_id not in queue:
                queue.append(job_id)
            f.seek(0)
            f.truncate()
            json.dump(queue, f, indent=2)
            f.write("\n")
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _pid_is_agy(pid: int) -> bool:
    """True only if this pid is official agy, not a recycled PID (e.g. chrome)."""
    try:
        os.kill(pid, 0)
        raw = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode("utf-8", "replace")
    except Exception:
        return False
    return "antigravity-cli/agy" in raw or raw.rstrip().endswith(" agy")


def find_running_job() -> str | None:
    if not os.path.isdir(JOBS):
        return None
    found = None
    newest = -1.0
    for name in os.listdir(JOBS):
        pidf = os.path.join(JOBS, name, "agy.pid")
        if not os.path.isfile(pidf):
            continue
        try:
            pid = int(open(pidf).read().strip())
        except Exception:
            continue
        if not _pid_is_agy(pid):
            continue
        mtime = os.path.getmtime(pidf)
        if mtime > newest:
            newest = mtime
            found = name
    return found


def _kill_tree(pid: int) -> None:
    """SIGTERM then SIGKILL a pid and its descendants. Never grok."""
    from windows import grok_pids

    if pid in grok_pids():
        return
    kids = []
    try:
        out = subprocess.check_output(["pgrep", "-P", str(pid)], text=True, stderr=subprocess.DEVNULL)
        kids = [int(x) for x in out.split() if x.strip().isdigit()]
    except Exception:
        pass
    for k in kids:
        _kill_tree(k)
    try:
        os.kill(pid, 15)
    except ProcessLookupError:
        return
    except Exception:
        pass
    time.sleep(0.3)
    try:
        os.kill(pid, 9)
    except Exception:
        pass


def kill_job(job_id: str | None = None) -> dict:
    """Stop a live AG job (and its children). Does not touch Grok."""
    import time as _time

    jid = job_id or find_running_job()
    if not jid:
        return {"status": "ERROR", "error": "no running AG job"}
    d = os.path.join(JOBS, jid)
    pid = None
    pidf = os.path.join(d, "agy.pid")
    if os.path.isfile(pidf):
        try:
            pid = int(open(pidf).read().strip())
        except Exception:
            pid = None
    if pid and _pid_is_agy(pid):
        try:
            os.killpg(pid, 15)
        except Exception:
            pass
        _kill_tree(pid)
    # supervisor
    try:
        out = subprocess.check_output(["pgrep", "-af", "job_supervisor.py " + jid], text=True)
        for line in out.splitlines():
            if "pgrep" in line:
                continue
            sp = int(line.split(None, 1)[0])
            _kill_tree(sp)
    except Exception:
        pass
    notify_path = os.path.join(d, "notify")
    with open(notify_path, "a") as f:
        f.write(f"CANCELED {jid}\n")
        f.flush()
    meta_path = os.path.join(d, "meta.json")
    meta = {}
    if os.path.isfile(meta_path):
        try:
            meta = json.load(open(meta_path))
        except Exception:
            meta = {}
    meta["phase"] = "done"
    meta["finish"] = "CANCELED"
    write_json(meta_path, meta)
    write_json(
        os.path.join(d, "result.json"),
        {"status": "CANCELED", "finish": "CANCELED", "job_id": jid, "finished": _now()},
    )
    return {"status": "CANCELED", "job_id": jid, "agy_pid": pid}


def spawn_job(
    task: str,
    cwd: str | None = None,
    model: str | None = None,
    timeout: str | None = None,
    continue_last: bool = False,
    conversation_id: str | None = None,
    new_session: bool = False,
) -> dict:
    cwd = os.path.expanduser(cwd or os.path.expanduser("~"))
    if not os.path.isdir(cwd):
        return {"status": "ERROR", "error": f"cwd does not exist: {cwd}"}
    if not task.strip():
        return {"status": "ERROR", "error": "empty task"}
    model = (model or DEFAULT_MODEL).strip()
    if any(b in model.lower() for b in BLOCKED):
        return {"status": "ERROR", "error": f"blocked model: {model}"}

    running = find_running_job()

    if new_session:
        forget(cwd)
        conversation_id = None
        continue_last = False
    elif not conversation_id:
        conversation_id = get_conversation(cwd)
        if conversation_id:
            continue_last = True

    job_id = str(uuid.uuid4())
    d = os.path.join(JOBS, job_id)
    os.makedirs(d, exist_ok=True)
    reuse = bool(conversation_id) and not new_session
    meta = {
        "job_id": job_id,
        "task": task,
        "cwd": cwd,
        "model": model or DEFAULT_MODEL,
        "timeout": timeout or DEFAULT_TIMEOUT,
        "continue_last": continue_last or reuse,
        "conversation_id": conversation_id,
        "new_project": not reuse and not continue_last and not conversation_id,
        "new_session": bool(new_session),
        "phase": "queued",
        "created": _now(),
    }
    write_json(os.path.join(d, "meta.json"), meta)
    open(os.path.join(d, "notify"), "a").close()
    log_path = os.path.join(d, "job.log")
    open(log_path, "a").close()

    if running:
        meta["behind"] = running
        write_json(os.path.join(d, "meta.json"), meta)
        queue_push(job_id)
        return {
            "status": "QUEUED",
            "job_id": job_id,
            "behind": running,
            "cwd": cwd,
            "model": meta["model"],
            "conversation_id": conversation_id,
            "new_project": meta["new_project"],
            "log": log_path,
            "notify": os.path.join(d, "notify"),
            "result": os.path.join(d, "result.json"),
            "preview_open": preview_open(),
            "watch": f"python3 {os.path.expanduser('~/.config/bridge/agy_cli/watch_job.py')} {job_id}",
            "note": f"Job queued behind running job {running}. Supervisor will start it automatically.",
        }

    env = os.environ.copy()
    env["DISPLAY"] = env.get("DISPLAY") or ":0.0"
    # Detached supervisor — not a child of Grok's tool process.
    subprocess.Popen(
        [os.environ.get("PYTHON", "python3"), SUPERVISOR, job_id],
        cwd=cwd,
        env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=open(os.path.join(d, "supervisor.err"), "a"),
    )

    how, preview_pid = ensure_preview(log_path, job_id, new_session=bool(new_session))
    if preview_pid:
        with open(os.path.join(d, "preview.pid"), "w") as f:
            f.write(str(preview_pid))
        meta["preview_pid"] = preview_pid
        write_json(os.path.join(d, "meta.json"), meta)

    return {
        "status": "STARTED",
        "job_id": job_id,
        "cwd": cwd,
        "model": meta["model"],
        "conversation_id": conversation_id,
        "new_project": meta["new_project"],
        "log": log_path,
        "notify": os.path.join(d, "notify"),
        "result": os.path.join(d, "result.json"),
        "how": how,
        "preview_pid": preview_pid,
        "preview_open": preview_open(),
        "watch": f"python3 {os.path.expanduser('~/.config/bridge/agy_cli/watch_job.py')} {job_id}",
        "note": (
            "AG is detached. Preview title is AG-job, not Grok's terminal. "
            "Same cwd continues the last AG conversation unless new_session=true. "
            "Logs stay open on finish; Grok is never closed."
        ),
    }


def read_job(job_id: str) -> dict:
    d = os.path.join(JOBS, job_id)
    out = {"job_id": job_id}
    for name in ("meta.json", "result.json"):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            try:
                with open(p) as f:
                    out[name.replace(".json", "")] = json.load(f)
            except Exception as e:
                out[name] = str(e)
    n = os.path.join(d, "notify")
    if os.path.isfile(n):
        out["notify"] = open(n).read().strip()
    pidf = os.path.join(d, "agy.pid")
    if os.path.isfile(pidf):
        try:
            pid = int(open(pidf).read().strip())
            os.kill(pid, 0)
            out["agy_alive"] = True
            out["agy_pid"] = pid
        except Exception:
            out["agy_alive"] = False
    out["preview_open"] = preview_open()
    if os.path.isfile(os.path.join(d, "preview_closed")):
        out["preview_closed"] = True
    if os.path.isfile(os.path.join(d, "preview_hidden")):
        out["preview_hidden"] = True
    return out

