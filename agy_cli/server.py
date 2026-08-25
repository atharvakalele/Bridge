#!/usr/bin/env python3
"""
agy-cli MCP — global Antigravity CLI worker.

Any client (Grok Build, Claude Code, Cline, etc.) can call these tools.
Runs official `agy -p` as a child process: start, wait, return status + reply.
Uses the signed-in Google / Gemini subscription (not an API key).
"""

import datetime
import json
import os
import shutil
import subprocess
import sys


def find_agy_bin() -> str:
    """Discover official Antigravity CLI binary location."""
    if os.environ.get("AGY_BIN"):
        return os.environ["AGY_BIN"]
    default_share = os.path.expanduser("~/.local/share/antigravity-cli/agy")
    if os.path.exists(default_share) and os.access(default_share, os.X_OK):
        return default_share
    which_agy = shutil.which("agy")
    if which_agy:
        return which_agy
    return default_share


AGY_BIN = find_agy_bin()
STATE_PATH = os.path.expanduser("~/.config/bridge/agy_cli/state.json")
DEFAULT_CWD = os.path.expanduser("~")
DEFAULT_TIMEOUT = os.environ.get("AGY_TIMEOUT", "15m")
DEFAULT_MODEL = os.environ.get("AGY_MODEL", "gemini-3.7-flash-medium")
BLOCKED_MODELS = ("opus", "claude-opus")


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def load_state() -> dict:
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(data: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def run_agy(
    task: str,
    cwd: str = None,
    model: str = None,
    timeout: str = None,
    continue_last: bool = False,
    conversation_id: str = None,
) -> dict:
    agy_binary = find_agy_bin()
    cwd = os.path.expanduser(cwd or DEFAULT_CWD)
    if not os.path.isdir(cwd):
        return {"status": "ERROR", "error": f"cwd does not exist: {cwd}"}
    timeout = timeout or DEFAULT_TIMEOUT
    model = model or DEFAULT_MODEL
    if any(b in (model or "").lower() for b in BLOCKED_MODELS):
        return {
            "status": "ERROR",
            "error": f"model {model} is blocked (quota). Use Gemini Flash only.",
        }
    state = load_state()

    prefix = (
        "You are Antigravity CLI invoked by a parent coding agent. "
        "Do not start waiter.sh or any long-running daemon. "
        "Do the task and finish so this process can exit.\n\n"
    )
    full_task = prefix + task

    args = [
        agy_binary,
        "-p",
        full_task,
        "--output-format",
        "json",
        "--print-timeout",
        str(timeout),
        "--dangerously-skip-permissions",
    ]
    args.extend(["--model", model])
    if conversation_id:
        args.extend(["--conversation", conversation_id])
    elif continue_last and state.get("last_conversation_id"):
        args.extend(["--conversation", state["last_conversation_id"]])
    else:
        args.append("--new-project")

    started = datetime.datetime.utcnow().isoformat() + "Z"
    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=None,
        )
    except Exception as e:
        return {"status": "ERROR", "error": str(e), "started": started}

    raw = (proc.stdout or "").strip()
    result = None
    if raw:
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # last JSON object if extra logs leaked
            for line in reversed(raw.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        result = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue
    if result is None:
        result = {
            "status": "ERROR",
            "error": f"agy produced no JSON (exit {proc.returncode})",
            "stderr_tail": (proc.stderr or "")[-2000:],
            "stdout_tail": raw[-2000:],
        }

    result["exit_code"] = proc.returncode
    result["started"] = started
    result["cwd"] = cwd
    result["model"] = model or "default"
    result["finished"] = datetime.datetime.utcnow().isoformat() + "Z"

    cid = result.get("conversation_id")
    if cid:
        state["last_conversation_id"] = cid
        state["last_status"] = result.get("status")
        state["last_cwd"] = cwd
        state["last_model"] = model
        state["updated"] = result["finished"]
        save_state(state)

    return result


def handle_run(args: dict) -> str:
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


def handle_models(_args=None) -> str:
    agy_binary = find_agy_bin()
    try:
        proc = subprocess.run(
            [agy_binary, "models"],
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


def handle_status(_args=None) -> str:
    return json.dumps(load_state() or {"status": "empty", "note": "no runs yet"})


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


def main() -> None:
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
