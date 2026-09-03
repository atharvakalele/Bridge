#!/usr/bin/env python3
"""Print one DONE/FAILED/TIMEOUT/... line when a job finishes. For Grok monitor."""
import os
import sys
import time

JOBS = os.path.expanduser("~/.config/bridge/agy_cli/jobs")
KINDS = ("SUCCESS", "ERROR", "CRASH", "TIMEOUT", "NETWORK", "CANCELED", "INTERRUPTED", "INVALID")


def main():
    if len(sys.argv) < 2:
        print("FAILED missing-job-id", flush=True)
        return 1
    job_id = sys.argv[1]
    path = os.path.join(JOBS, job_id, "notify")
    deadline = time.time() + int(os.environ.get("AGY_WATCH_SEC", "86400"))
    pos = 0
    while time.time() < deadline:
        if os.path.isfile(path):
            with open(path) as f:
                f.seek(pos)
                chunk = f.read()
                pos = f.tell()
            for line in chunk.splitlines():
                kind = (line.split() or [""])[0].upper()
                if kind in KINDS:
                    print(f"{kind} {job_id}", flush=True)
                    return 0 if kind == "SUCCESS" else 1
        time.sleep(0.4)
    print(f"TIMEOUT {job_id}", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
