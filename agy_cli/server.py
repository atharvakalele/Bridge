#!/usr/bin/env python3
"""
agy-cli MCP — global Antigravity CLI worker.

Any client (Grok Build, Claude Code, etc.) can call these tools.
Runs official `agy -p` as a child process: start, wait, return status + reply.
Uses the signed-in Google / Gemini subscription (not an API key).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runner import load_state  # noqa: E402
from spawn_job import spawn_job, read_job  # noqa: E402


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def handle_run(args):
    """Fire-and-forget: detach AG, open preview terminal, return job_id now."""
    return json.dumps(
        spawn_job(
            task=args.get("task") or "",
            cwd=args.get("cwd"),
            model=args.get("model"),
            timeout=args.get("timeout"),
            continue_last=bool(args.get("continue_last")),
            conversation_id=args.get("conversation_id"),
            new_session=bool(args.get("new_session")),
        )
    )


def handle_models(_args=None):
    import subprocess
    from runner import AGY_BIN

    try:
        proc = subprocess.run(
            [AGY_BIN, "models"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return json.dumps(
            {
                "status": "SUCCESS" if proc.returncode == 0 else "ERROR",
                "exit_code": proc.returncode,
                "models_text": proc.stdout,
                "note": (
                    "Pass a slug as the 'model' argument to agy_run. "
                    "Uses the signed-in Gemini/Antigravity subscription, not an API key. "
                    "Omit model to use CLI default."
                ),
            }
        )
    except Exception as e:
        return json.dumps({"status": "ERROR", "error": str(e)})


def handle_status(args=None):
    args = args or {}
    job_id = args.get("job_id") or (load_state() or {}).get("last_job_id")
    if job_id:
        return json.dumps(read_job(job_id))
    return json.dumps(load_state() or {"status": "empty", "note": "no runs yet"})


TOOLS = [
    {
        "name": "agy_run",
        "description": (
            "FIRE-AND-FORGET Antigravity CLI. Starts a detached job (survives this chat), "
            "opens/reuses one visible AG CLI terminal, returns job_id immediately. "
            "Same cwd continues the last AG conversation (history). Pass new_session=true to start fresh. "
            "Then run: python3 ~/.config/bridge/agy_cli/watch_job.py <job_id>  as a background monitor "
            "(prints SUCCESS/ERROR/CRASH/TIMEOUT/NETWORK). Do not block this turn waiting on AG. "
            "SUCCESS closes the preview window; failures leave it open. Do not start waiter.sh."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Full task for Antigravity CLI to execute.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (absolute). Default: home.",
                },
                "model": {
                    "type": "string",
                    "description": (
                        "Optional slug. Default is gemini-3.7-flash-medium. "
                        "Never use Claude Opus or Gemini Pro unless the user overrides in writing."
                    ),
                },
                "timeout": {
                    "type": "string",
                    "description": "Print timeout, e.g. 60s, 15m. Default 15m.",
                },
                "continue_last": {
                    "type": "boolean",
                    "description": "Force continue last AG chat. Default already continues per cwd if known.",
                },
                "conversation_id": {
                    "type": "string",
                    "description": "Resume a specific AG CLI conversation id.",
                },
                "new_session": {
                    "type": "boolean",
                    "description": "Start a new AG conversation (forget cwd history). Default false.",
                },
            },
            "required": ["task"],
        },
    },
    {
        "name": "agy_models",
        "description": "List Antigravity CLI model slugs available on this account.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "agy_status",
        "description": "Status of an AG job (notify/result/alive). Defaults to last job.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "From agy_run. Optional."}
            },
            "required": [],
        },
    },
]


def main():
    log("agy-cli MCP ready (official agy child process)")
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            req = json.loads(line)
            method = req.get("method", "")
            req_id = req.get("id")

            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "agy-cli", "version": "1.0.0"},
                    },
                }
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": TOOLS},
                }
            elif method == "tools/call":
                params = req.get("params", {})
                name = params.get("name", "")
                args = params.get("arguments", {}) or {}
                if name == "agy_run":
                    text = handle_run(args)
                elif name == "agy_models":
                    text = handle_models(args)
                elif name == "agy_status":
                    text = handle_status(args)
                else:
                    print(
                        json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "id": req_id,
                                "error": {"code": -32601, "message": f"Unknown tool: {name}"},
                            }
                        ),
                        flush=True,
                    )
                    continue
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": text}]},
                }
            else:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not supported: {method}"},
                }
            print(json.dumps(resp), flush=True)
        except Exception as e:
            log(f"Error: {e}")
            if "req_id" in locals() and req_id:
                print(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32603, "message": str(e)},
                        }
                    ),
                    flush=True,
                )


if __name__ == "__main__":
    main()
