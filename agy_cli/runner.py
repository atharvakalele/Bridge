#!/usr/bin/env python3
"""Run official agy in print mode and return as soon as a result event exists.

agy --output-format json waits for WaitForConversationFullyIdle. If AG leaves a
background tool running, that wait looks hung and then times out — even after
the model already answered. Stream-json emits `result` first; we take that and
stop the child.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import datetime
import shutil
import shlex

AGY_BIN = os.environ.get(
    "AGY_BIN",
    os.path.expanduser("~/.local/share/antigravity-cli/agy"),
)
if not os.path.isfile(AGY_BIN):
    AGY_BIN = shutil.which("agy") or AGY_BIN

STATE_PATH = os.path.expanduser("~/.config/bridge/agy_cli/state.json")
PROGRESS_PATH = os.environ.get("AGY_PROGRESS", "/tmp/agy-job.progress")
DEFAULT_MODEL = os.environ.get("AGY_MODEL", "gemini-3.7-flash-medium")
DEFAULT_TIMEOUT = os.environ.get("AGY_TIMEOUT", "15m")
BLOCKED = ("opus", "claude-opus")


def _now():
    return datetime.datetime.utcnow().isoformat() + "Z"


def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(data):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def write_progress(obj):
    tmp = PROGRESS_PATH + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(obj, f)
        os.replace(tmp, PROGRESS_PATH)
    except Exception:
        pass


def start_agy_terminal(
    task,
    cwd=None,
    model=None,
    timeout=None,
    continue_last=False,
    conversation_id=None,
    new_project=True,
):
    """Open a visible xfce4-terminal running official agy. Do not wait. Never kill it."""
    cwd = os.path.expanduser(cwd or os.path.expanduser("~"))
    if not os.path.isdir(cwd):
        return {"status": "ERROR", "error": f"cwd does not exist: {cwd}"}

    timeout = timeout or DEFAULT_TIMEOUT
    model = (model or "").strip()
    if model and any(b in model.lower() for b in BLOCKED):
        return {"status": "ERROR", "error": f"model {model} is blocked (quota)."}

    if not os.path.isfile(AGY_BIN) and not shutil.which(AGY_BIN):
        return {"status": "ERROR", "error": f"agy binary not found: {AGY_BIN}"}

    # One visible AG job. A second window would fight the first.
    try:
        out = subprocess.check_output(["pgrep", "-ax", "agy"], text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        out = ""
    if "/antigravity-cli/agy" in out or out.strip().endswith(" agy") or "\nagy " in out:
        for line in out.splitlines():
            if "antigravity-cli/agy" in line or line.strip().endswith("agy"):
                pid = int(line.split()[0])
                return {
                    "status": "ALREADY_RUNNING",
                    "pid": pid,
                    "note": "Visible AG already up. Not starting a second. Use agy_status.",
                }

    task_file = "/tmp/agy-term-task.txt"
    with open(task_file, "w") as f:
        f.write(task)

    state = load_state()
    prefix = (
        "You are Antigravity CLI in a visible terminal. "
        "Do not start waiter.sh. Do the task and finish.\n\n"
    )
    args = [
        AGY_BIN,
        "-p",
        prefix + task,
        "--output-format",
        "stream-json",
        "--print-timeout",
        str(timeout),
        "--dangerously-skip-permissions",
    ]
    if model:
        args.extend(["--model", model])
    if conversation_id:
        args.extend(["--conversation", conversation_id])
    elif continue_last and state.get("last_conversation_id"):
        args.extend(["--conversation", state["last_conversation_id"]])
    elif new_project:
        args.append("--new-project")

    log_path = "/tmp/agy-term.log"
    runner = "/tmp/run-agy-term.sh"
    # quote args safely
    quoted = " ".join(shlex.quote(a) for a in args)
    with open(runner, "w") as f:
        f.write("#!/usr/bin/env bash\nset -u\n")
        f.write(f"cd {shlex.quote(cwd)}\n")
        f.write(f"export DISPLAY=${{DISPLAY:-:0.0}}\n")
        f.write(f"stdbuf -oL -eL {quoted} 2>&1 | tee {shlex.quote(log_path)}\n")
        f.write("echo AG_EXIT:$?\n")
    os.chmod(runner, 0o755)

    display = os.environ.get("DISPLAY", ":0.0")
    env = os.environ.copy()
    env["DISPLAY"] = display
    if shutil.which("xfce4-terminal"):
        subprocess.Popen(
            [
                "xfce4-terminal",
                "--disable-server",
                "--title=AG-job legacy",
                "--geometry=110x36+200+80",
                "-e",
                runner,
            ],
            env=env,
            start_new_session=True,
        )
        how = "xfce4-terminal"
    else:
        subprocess.Popen(
            ["bash", runner],
            env=env,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        how = "nohup-bash"

    started = _now()
    write_progress(
        {
            "phase": "detached",
            "cwd": cwd,
            "model": model or "cli-default",
            "started": started,
            "how": how,
            "log": log_path,
        }
    )
    state.update(
        {
            "last_status": "DETACHED",
            "last_cwd": cwd,
            "last_model": model or "cli-default",
            "updated": started,
            "log": log_path,
        }
    )
    save_state(state)
    return {
        "status": "STARTED",
        "how": how,
        "cwd": cwd,
        "log": log_path,
        "note": "AG is in its own terminal. Grok chat will not kill it. Poll agy_status.",
    }


def run_agy(
    task,
    cwd=None,
    model=None,
    timeout=None,
    continue_last=False,
    conversation_id=None,
    new_project=True,
):
    cwd = os.path.expanduser(cwd or os.path.expanduser("~"))
    if not os.path.isdir(cwd):
        return {"status": "ERROR", "error": f"cwd does not exist: {cwd}"}

    timeout = timeout or DEFAULT_TIMEOUT
    model = model or DEFAULT_MODEL
    if any(b in model.lower() for b in BLOCKED):
        return {"status": "ERROR", "error": f"model {model} is blocked (quota)."}

    if not os.path.isfile(AGY_BIN) and not shutil.which(AGY_BIN):
        return {"status": "ERROR", "error": f"agy binary not found: {AGY_BIN}"}

    state = load_state()
    prefix = (
        "You are Antigravity CLI invoked by a parent coding agent. "
        "Do not start waiter.sh or any long-running daemon. "
        "Do the task and finish so this process can exit.\n\n"
    )
    args = [
        AGY_BIN,
        "-p",
        prefix + task,
        "--output-format",
        "stream-json",
        "--print-timeout",
        str(timeout),
        "--dangerously-skip-permissions",
        "--model",
        model,
    ]
    if conversation_id:
        args.extend(["--conversation", conversation_id])
    elif continue_last and state.get("last_conversation_id"):
        args.extend(["--conversation", state["last_conversation_id"]])
    elif new_project:
        args.append("--new-project")

    started = _now()
    write_progress(
        {
            "phase": "starting",
            "cwd": cwd,
            "model": model,
            "started": started,
            "last_event": None,
        }
    )

    proc = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    result = None
    last_event = None
    stderr_chunks = []

    def _kill():
        if proc.poll() is None:
            try:
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except Exception:
                pass

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            last_event = ev.get("event")
            write_progress(
                {
                    "phase": "running",
                    "cwd": cwd,
                    "model": model,
                    "started": started,
                    "pid": proc.pid,
                    "last_event": last_event,
                    "updated": _now(),
                    "conversation_id": ev.get("conversation_id")
                    or (ev.get("result") or {}).get("conversation_id"),
                }
            )
            if ev.get("event") == "result" and isinstance(ev.get("result"), dict):
                result = ev["result"]
                _kill()
                break
    except Exception as e:
        _kill()
        return {"status": "ERROR", "error": str(e), "started": started}

    if proc.stderr:
        try:
            stderr_chunks.append(proc.stderr.read() or "")
        except Exception:
            pass

    rc = proc.poll()
    if rc is None:
        _kill()
        rc = proc.poll()

    if result is None:
        result = {
            "status": "ERROR",
            "error": "agy produced no result event (hung or crashed before finish)",
            "stderr_tail": "".join(stderr_chunks)[-2000:],
            "last_event": last_event,
        }

    result["exit_code"] = rc
    result["started"] = started
    result["cwd"] = cwd
    result["model"] = model
    result["finished"] = _now()
    result["stopped_on_result"] = True

    cid = result.get("conversation_id")
    if cid:
        state.update(
            {
                "last_conversation_id": cid,
                "last_status": result.get("status"),
                "last_cwd": cwd,
                "last_model": model,
                "updated": result["finished"],
            }
        )
        save_state(state)

    write_progress({"phase": "done", "result_status": result.get("status"), "updated": _now()})
    return result
