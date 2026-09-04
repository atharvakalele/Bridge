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

FINISH_EXPLANATIONS = {
    "SUCCESS": "Task completed successfully with result status SUCCESS.",
    "ERROR": "Antigravity reported an error during task execution.",
    "CRASH": "The agy process died or exited without emitting a final result event.",
    "TIMEOUT": "Execution hit the wall-clock timeout limit and was stopped by the supervisor.",
    "NETWORK": "Network, authentication, quota, rate limit (429), or server error (5xx) occurred.",
    "CANCELED": "Job was canceled or interrupted before completion.",
}


def explain_finish(kind: str) -> str:
    """Return a plain-English explanation of why the job finished with this status."""
    return FINISH_EXPLANATIONS.get(kind.upper(), f"Job finished with status {kind}.")


def parse_timeout(val: str | int | float | None) -> float:
    """Parse timeout string like '15m', '60s', '2h' into seconds (float)."""
    if val is None:
        return 900.0  # 15m default
    if isinstance(val, (int, float)):
        return max(1.0, float(val))
    s = str(val).strip().lower()
    if not s:
        return 900.0
    try:
        if s.endswith("ms"):
            return max(0.1, float(s[:-2]) / 1000.0)
        if s.endswith("s"):
            return max(1.0, float(s[:-1]))
        if s.endswith("m"):
            return max(1.0, float(s[:-1]) * 60.0)
        if s.endswith("h"):
            return max(1.0, float(s[:-1]) * 3600.0)
        if s.endswith("d"):
            return max(1.0, float(s[:-1]) * 86400.0)
        return max(1.0, float(s))
    except ValueError:
        return 900.0


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
    """Deprecated alias. Live path is spawn_job (detached)."""
    from spawn_job import spawn_job
    return spawn_job(
        task=task,
        cwd=cwd,
        model=model,
        timeout=timeout,
        continue_last=continue_last,
        conversation_id=conversation_id,
        new_session=bool(new_project) and not continue_last and not conversation_id,
    )



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
        "You are Antigravity CLI invoked by a parent coding agent. Do the assigned task and exit.\n"
        "Never start waiter.sh, grok_waiter.sh, or any long-running daemon.\n"
        "Long llama/harness scripts (run_qwen36.sh, run_qwen38.sh, run_server_ring.sh, gate.sh, build) ARE ALLOWED and expected to take time.\n"
        "When running ring/harness/llama commands via run_command, set WaitMsBeforeAsync or manage them with timeout >= 15m.\n"
        "NEVER run 'pkill -f llama' or 'pkill llama-cli' without -x on the desktop machine (it matches the agy process argv and kills this agent).\n\n"
    )
    timeout_sec = int(parse_timeout(timeout or DEFAULT_TIMEOUT))
    duration_str = f"{timeout_sec}s"
    args = [
        AGY_BIN,
        "-p",
        prefix + task,
        "--output-format",
        "stream-json",
        "--print-timeout",
        duration_str,
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
