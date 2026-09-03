#!/usr/bin/env python3
"""Create a job, detach the supervisor, open a preview terminal. Return immediately."""
from __future__ import annotations

import json
import os
import subprocess
import uuid

from runner import BLOCKED, DEFAULT_MODEL, DEFAULT_TIMEOUT, _now
from sessions import forget, get_conversation
from windows import ensure_preview


def write_json(path: str, obj: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)

# job_supervisor JOBS constant — keep in sync
JOBS = os.path.expanduser("~/.config/bridge/agy_cli/jobs")
SUPERVISOR = os.path.expanduser("~/.config/bridge/agy_cli/job_supervisor.py")


def find_running_job() -> str | None:
    if not os.path.isdir(JOBS):
        return None
    for name in os.listdir(JOBS):
        pidf = os.path.join(JOBS, name, "agy.pid")
        if not os.path.isfile(pidf):
            continue
        try:
            pid = int(open(pidf).read().strip())
            os.kill(pid, 0)
            return name
        except Exception:
            continue
    return None


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
    if running:
        return {
            "status": "ALREADY_RUNNING",
            "job_id": running,
            "error": "An AG job is already running. Wait for it; do not open a second window.",
        }

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
        "watch": f"python3 {os.path.expanduser('~/.config/bridge/agy_cli/watch_job.py')} {job_id}",
        "note": (
            "AG is detached. Preview title is AG-job <id>, not Grok's terminal. "
            "Same cwd continues the last AG conversation unless new_session=true. "
            "SUCCESS closes only that preview PID; Grok is never closed."
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
    return out
