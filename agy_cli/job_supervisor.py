#!/usr/bin/env python3
"""Supervise one AG CLI job outside Grok's process tree.

- Runs official agy (stream-json) as its own session
- Tees human-readable + raw events to a log
- Classifies every finish: SUCCESS, ERROR, CRASH, TIMEOUT, NETWORK, CANCELED
- Writes result.json and a one-line notify file so the parent can wake
- Does not die if the preview terminal is closed
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runner import AGY_BIN, BLOCKED, DEFAULT_MODEL, DEFAULT_TIMEOUT, load_state, save_state, _now  # noqa: E402
from sessions import remember  # noqa: E402
from windows import append_preview, close_if_success  # noqa: E402

JOBS = os.path.expanduser("~/.config/bridge/agy_cli/jobs")
NETWORK_MARKERS = (
    "connection refused",
    "network is unreachable",
    "temporary failure in name resolution",
    "failed to fetch",
    "tls handshake",
    "i/o timeout",
    "connection reset",
    "dial tcp",
    "no route to host",
    "authentication required",
    "status=401",
    "status=403",
    "status=429",
    "status=500",
    "status=502",
    "status=503",
)


def job_dir(job_id: str) -> str:
    return os.path.join(JOBS, job_id)


def write_json(path: str, obj: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def notify(job_id: str, kind: str, extra: str = "") -> None:
    line = kind if not extra else f"{kind} {extra}"
    path = os.path.join(job_dir(job_id), "notify")
    with open(path, "a") as f:
        f.write(line.strip() + "\n")
        f.flush()
        os.fsync(f.fileno())


def classify(result: dict | None, rc: int | None, log_tail: str, timed_out: bool) -> str:
    if timed_out:
        return "TIMEOUT"
    low = (log_tail or "").lower()
    if any(m in low for m in NETWORK_MARKERS):
        return "NETWORK"
    if result:
        st = (result.get("status") or "").upper()
        if st == "SUCCESS":
            return "SUCCESS"
        if st in ("ERROR", "CANCELED", "INTERRUPTED", "INVALID"):
            return st
        return "ERROR"
    if rc is None:
        return "TIMEOUT"
    if rc < 0:
        return "CANCELED"
    if rc != 0:
        return "CRASH"
    return "CRASH"


def build_agy_args(task, model, timeout, conversation_id, continue_last, new_project):
    model = model or DEFAULT_MODEL
    if any(b in model.lower() for b in BLOCKED):
        raise ValueError(f"blocked model: {model}")
    prefix = (
        "You are Antigravity CLI in a detached visible job. "
        "Do not start waiter.sh or long-running daemons. "
        "Do the task and finish.\n\n"
    )
    args = [
        AGY_BIN,
        "-p",
        prefix + task,
        "--output-format",
        "stream-json",
        "--print-timeout",
        str(timeout or DEFAULT_TIMEOUT),
        "--dangerously-skip-permissions",
        "--model",
        model,
    ]
    state = load_state()
    if conversation_id:
        args.extend(["--conversation", conversation_id])
    elif continue_last and state.get("last_conversation_id"):
        args.extend(["--conversation", state["last_conversation_id"]])
    elif continue_last:
        args.append("--continue")
    elif new_project:
        args.append("--new-project")
    return args, model


def run_job(job_id: str) -> int:
    d = job_dir(job_id)
    meta_path = os.path.join(d, "meta.json")
    log_path = os.path.join(d, "job.log")
    raw_path = os.path.join(d, "stream.ndjson")
    result_path = os.path.join(d, "result.json")
    pid_path = os.path.join(d, "agy.pid")

    with open(meta_path) as f:
        meta = json.load(f)
    task = meta["task"]
    cwd = meta.get("cwd") or os.path.expanduser("~")
    model = meta.get("model")
    timeout = meta.get("timeout") or DEFAULT_TIMEOUT
    try:
        args, model = build_agy_args(
            task,
            model,
            timeout,
            meta.get("conversation_id"),
            bool(meta.get("continue_last")),
            meta.get("new_project", True),
        )
    except ValueError as e:
        payload = {
            "status": "ERROR",
            "finish": "ERROR",
            "error": str(e),
            "job_id": job_id,
            "finished": _now(),
        }
        write_json(result_path, payload)
        notify(job_id, "ERROR", job_id)
        meta["phase"] = "done"
        meta["finish"] = "ERROR"
        write_json(meta_path, meta)
        return 1

    meta.update({"phase": "running", "started": _now(), "model": model})
    write_json(meta_path, meta)

    logf = open(log_path, "a", buffering=1)
    rawf = open(raw_path, "a", buffering=1)

    def banner(msg: str) -> None:
        line = f"\n======== {msg} ========\n"
        logf.write(line)
        append_preview(line)
        sys.stdout.write(line)
        sys.stdout.flush()

    banner(f"AG JOB {job_id}")
    logf.write(f"cwd={cwd}\nmodel={model}\ntimeout={timeout}\n")
    logf.write("--- TASK ---\n")
    logf.write(task.rstrip() + "\n")
    logf.write("--- AG OUTPUT ---\n")
    logf.flush()
    sys.stdout.write(f"cwd={cwd} model={model}\n--- TASK ---\n{task}\n--- AG OUTPUT ---\n")
    sys.stdout.flush()

    proc = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    with open(pid_path, "w") as f:
        f.write(str(proc.pid))

    result = None
    timed_out = False
    log_tail_chunks: list[str] = []

    def stop_agy() -> None:
        if proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                proc.kill()

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            rawf.write(line)
            rawf.flush()
            show = line
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                ev = None
            if ev and ev.get("event") == "step_update":
                s = ev.get("step_update") or {}
                bits = [
                    s.get("state"),
                    s.get("step_type"),
                    s.get("tool_name") or "",
                    (s.get("text_delta") or "")[:200],
                ]
                show = " ".join(x for x in bits if x) + "\n"
            elif ev and ev.get("event") == "result":
                result = ev.get("result") if isinstance(ev.get("result"), dict) else None
                show = f"[result] {(result or {}).get('status')}\n"
            logf.write(show)
            logf.flush()
            append_preview(show)
            sys.stdout.write(show)
            sys.stdout.flush()
            log_tail_chunks.append(show)
            if len(log_tail_chunks) > 200:
                log_tail_chunks = log_tail_chunks[-200:]
            if result is not None:
                stop_agy()
                break
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        timed_out = True
        stop_agy()
    except Exception:
        logf.write(traceback.format_exc())
        stop_agy()
    finally:
        rc = proc.poll()
        tail = "".join(log_tail_chunks)[-4000:]
        kind = classify(result, rc, tail, timed_out)
        payload = result or {}
        payload.update(
            {
                "finish": kind,
                "job_id": job_id,
                "exit_code": rc,
                "cwd": cwd,
                "model": model,
                "finished": _now(),
                "log": log_path,
            }
        )
        if kind != "SUCCESS" and not payload.get("error"):
            payload["error"] = kind
        write_json(result_path, payload)
        st = load_state()
        st.update(
            {
                "last_job_id": job_id,
                "last_conversation_id": payload.get("conversation_id"),
                "last_status": kind,
                "last_cwd": cwd,
                "last_model": model,
                "updated": payload["finished"],
                "log": log_path,
            }
        )
        save_state(st)
        remember(cwd, payload.get("conversation_id"), job_id=job_id, status=kind)
        preview_pid = meta.get("preview_pid")
        if not preview_pid:
            pidf = os.path.join(d, "preview.pid")
            if os.path.isfile(pidf):
                try:
                    preview_pid = int(open(pidf).read().strip())
                except Exception:
                    preview_pid = None
        close_if_success(kind, preview_pid)
        banner(f"FINISHED {kind}")
        if payload.get("response"):
            sys.stdout.write((payload["response"] or "")[:4000] + "\n")
            sys.stdout.flush()
        notify(job_id, kind, job_id)
        logf.close()
        rawf.close()
        meta["phase"] = "done"
        meta["finish"] = kind
        meta["finished"] = payload["finished"]
        write_json(meta_path, meta)
        return 0 if kind == "SUCCESS" else 1


def main():
    if len(sys.argv) < 2:
        print("usage: job_supervisor.py <job_id>", file=sys.stderr)
        return 2
    return run_job(sys.argv[1])


if __name__ == "__main__":
    raise SystemExit(main())
