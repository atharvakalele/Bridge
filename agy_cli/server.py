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
from runner import run_agy, load_state, PROGRESS_PATH  # noqa: E402


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def handle_run(args):
    return json.dumps(
        run_agy(
            task=args.get("task") or "",
            cwd=args.get("cwd"),
            model=args.get("model"),
            timeout=args.get("timeout"),
            continue_last=bool(args.get("continue_last")),
            conversation_id=args.get("conversation_id"),
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


def handle_status(_args=None):
    st = load_state() or {}
    try:
        with open(PROGRESS_PATH) as f:
            st["live"] = json.load(f)
    except Exception:
        st["live"] = None
    return json.dumps(st or {"status": "empty", "note": "no runs yet"})


TOOLS = [
    {
        "name": "agy_run",
        "description": (
            "Collaborate with Antigravity CLI (agy). Runs official agy as a child process "
            "on the user's Gemini subscription (not API). Blocks until AG finishes and "
            "returns status, conversation_id, and response. Use whenever the user says "
            "collaborate with AG, use AG CLI, or delegate to Antigravity. "
            "Do not start waiter.sh. Chat IDs are managed here automatically."
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
                    "description": "Continue the last AG CLI conversation instead of starting new.",
                },
                "conversation_id": {
                    "type": "string",
                    "description": "Resume a specific AG CLI conversation id.",
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
        "description": "Last AG CLI run: conversation_id, status, cwd, model.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
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
