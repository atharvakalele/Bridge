#!/usr/bin/env python3
"""Supervise one AG CLI job outside Grok's process tree.

- Runs official agy (stream-json) as its own session
- Tees human-readable + raw events to a log
- Classifies every finish: SUCCESS, ERROR, CRASH, TIMEOUT, NETWORK, CANCELED
- Writes result.json and a one-line notify file so the parent can wake
- Does not die if the preview terminal is closed
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runner import (  # noqa: E402
    AGY_BIN,
    BLOCKED,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    load_state,
    save_state,
    _now,
    parse_timeout,
    explain_finish,
)
from sessions import remember  # noqa: E402
from windows import append_preview, close_if_success, preview_open  # noqa: E402

JOBS = os.path.expanduser("~/.config/bridge/agy_cli/jobs")
SUPERVISOR = os.path.expanduser("~/.config/bridge/agy_cli/job_supervisor.py")
QUEUE_FILE = os.path.expanduser("~/.config/bridge/agy_cli/queue.json")

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
    "quota reached",
    "individual quota",
    "rate limit",
    "resource exhausted",
    "resets in",
)

# Antigravity: "Individual quota reached. ... Resets in 2m33s."
_QUOTA_RESET_RE = re.compile(
    r"resets in\s+(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?",
    re.I,
)


def parse_quota_reset_seconds(text: str) -> float | None:
    """Return wait seconds from an Antigravity quota error, or None."""
    if not text:
        return None
    m = _QUOTA_RESET_RE.search(text)
    if not m:
        return None
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    total = h * 3600 + mi * 60 + s
    return float(total) if total > 0 else None


def job_dir(job_id: str) -> str:
    return os.path.join(JOBS, job_id)


def write_json(path: str, obj: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def queue_pop_next() -> str | None:
    if not os.path.isfile(QUEUE_FILE):
        return None
    try:
        with open(QUEUE_FILE, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.seek(0)
                content = f.read().strip()
                queue = json.loads(content) if content else []
                if not isinstance(queue, list):
                    queue = []
                next_id = None
                remaining = []
                for jid in queue:
                    if next_id is None:
                        meta_p = os.path.join(JOBS, jid, "meta.json")
                        res_p = os.path.join(JOBS, jid, "result.json")
                        is_done = False
                        if os.path.isfile(res_p):
                            is_done = True
                        elif os.path.isfile(meta_p):
                            try:
                                with open(meta_p) as mf:
                                    m = json.load(mf)
                                    if m.get("phase") == "done":
                                        is_done = True
                            except Exception:
                                pass
                        if not is_done and os.path.isdir(os.path.join(JOBS, jid)):
                            next_id = jid
                        else:
                            continue
                    else:
                        remaining.append(jid)
                f.seek(0)
                f.truncate()
                json.dump(remaining, f, indent=2)
                f.write("\n")
                f.flush()
                return next_id
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception:
        return None


def notify(job_id: str, kind: str, extra: str = "") -> None:
    line = kind if not extra else f"{kind} {extra}"
    path = os.path.join(job_dir(job_id), "notify")
    with open(path, "a") as f:
        f.write(line.strip() + "\n")
        f.flush()
        os.fsync(f.fileno())


def classify(
    result: dict | None,
    rc: int | None,
    log_tail: str,
    timed_out: bool,
    user_canceled: bool = False,
) -> str:
    """Classify job termination into standard finish kinds:
    SUCCESS: result status was SUCCESS.
    ERROR: Antigravity CLI returned an error status.
    CRASH: Process died/exited with no result event (e.g. unexpected SIGKILL rc=-9).
    TIMEOUT: Wall-clock deadline was exceeded and supervisor terminated the process.
    NETWORK: Connection, TLS, DNS, auth, or HTTP 429/5xx error detected.
    CANCELED: Job was canceled by user/kill_job (SIGINT/SIGTERM or explicit cancel).
    """
    if timed_out:
        return "TIMEOUT"
    if user_canceled:
        return "CANCELED"
    err_text = ""
    if result and isinstance(result, dict):
        err_text = str(result.get("error") or "")
    low = (log_tail or "").lower() + " " + err_text.lower()
    if any(m in low for m in NETWORK_MARKERS):
        return "NETWORK"
    if result:
        st = (result.get("status") or "").upper()
        if st == "SUCCESS":
            return "SUCCESS"
        if st in ("ERROR", "INVALID", "FAILED"):
            return "ERROR"
        if st in ("CANCELED", "CANCELLED", "INTERRUPTED"):
            return "CANCELED"
        if st == "TIMEOUT":
            return "TIMEOUT"
        return "ERROR"
    if rc is None:
        return "TIMEOUT"
    if rc in (130, 143) and user_canceled:
        return "CANCELED"
    if rc != 0:
        return "CRASH"
    return "CRASH"


def build_agy_args(task, model, timeout, conversation_id, continue_last, new_project):
    model = model or DEFAULT_MODEL
    if any(b in model.lower() for b in BLOCKED):
        raise ValueError(f"blocked model: {model}")
    prefix = (
        "You are Antigravity CLI in a detached visible job. Do the assigned task and exit.\n"
        "Never start waiter.sh, grok_waiter.sh, or any long-running poll daemon.\n"
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
            "finish_reason": explain_finish("ERROR"),
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

    # Enforce wall-clock deadline
    timeout_sec = parse_timeout(timeout)
    deadline = time.time() + timeout_sec
    preview_closed_flag = False

    def watchdog() -> None:
        nonlocal timed_out, preview_closed_flag
        while proc.poll() is None and not timed_out:
            if time.time() >= deadline:
                timed_out = True
                stop_agy()
                break
            if not preview_open():
                if not preview_closed_flag:
                    preview_closed_flag = True
                    try:
                        meta["preview_closed"] = True
                        write_json(meta_path, meta)
                        open(os.path.join(d, "preview_closed"), "w").close()
                    except Exception:
                        pass
            time.sleep(0.5)

    wd_thread = threading.Thread(target=watchdog, daemon=True)
    wd_thread.start()

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
        user_canceled = False
        notify_path = os.path.join(d, "notify")
        if os.path.isfile(notify_path):
            try:
                with open(notify_path) as nf:
                    user_canceled = any(l.strip().startswith("CANCELED") for l in nf)
            except Exception:
                pass
        kind = classify(result, rc, tail, timed_out, user_canceled=user_canceled)
        err_now = ""
        if result and isinstance(result, dict):
            err_now = str(result.get("error") or "")
        wait_s = parse_quota_reset_seconds(err_now)
        quota_hit = kind == "NETWORK" and wait_s is not None and "quota" in err_now.lower()
        if quota_hit and not meta.get("quota_retried") and wait_s <= 600:
            meta["quota_retried"] = True
            write_json(meta_path, meta)
            wait_s = wait_s + 8
            banner(f"QUOTA retry in {int(wait_s)}s: {err_now[:180]}")
            logf.flush()
            try:
                logf.close()
            except Exception:
                pass
            try:
                rawf.close()
            except Exception:
                pass
            time.sleep(wait_s)
            return run_job(job_id)
        payload = result or {}
        payload.update(
            {
                "finish": kind,
                "finish_reason": explain_finish(kind),
                "job_id": job_id,
                "exit_code": rc,
                "cwd": cwd,
                "model": model,
                "finished": _now(),
                "log": log_path,
            }
        )
        if kind != "SUCCESS" and not payload.get("error"):
            payload["error"] = kind if kind != "TIMEOUT" else f"Job exceeded timeout ({timeout})"
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
        if not user_canceled or kind != "CANCELED":
            extra = job_id
            err_bit = str(payload.get("error") or "")[:180].replace("\n", " ")
            if err_bit:
                extra = f"{job_id} {err_bit}"
            notify(job_id, kind, extra)
        logf.close()
        rawf.close()
        meta["phase"] = "done"
        meta["finish"] = kind
        meta["finished"] = payload["finished"]
        write_json(meta_path, meta)

        # Pop the next queued id and start job_supervisor.py for it (FIFO)
        next_job_id = queue_pop_next()
        if next_job_id:
            next_d = job_dir(next_job_id)
            next_meta_path = os.path.join(next_d, "meta.json")
            next_cwd = os.path.expanduser("~")
            if os.path.isfile(next_meta_path):
                try:
                    with open(next_meta_path) as mf:
                        next_cwd = json.load(mf).get("cwd") or next_cwd
                except Exception:
                    pass
            next_env = os.environ.copy()
            next_env["DISPLAY"] = next_env.get("DISPLAY") or ":0.0"
            subprocess.Popen(
                [os.environ.get("PYTHON", "python3"), SUPERVISOR, next_job_id],
                cwd=next_cwd,
                env=next_env,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=open(os.path.join(next_d, "supervisor.err"), "a"),
            )

        return 0 if kind == "SUCCESS" else 1


def main():
    if len(sys.argv) < 2:
        print("usage: job_supervisor.py <job_id>", file=sys.stderr)
        return 2
    return run_job(sys.argv[1])


if __name__ == "__main__":
    raise SystemExit(main())

