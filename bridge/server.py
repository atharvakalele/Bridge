#!/usr/bin/env python3
"""
Antigravity IDE Bridge — Bidirectional Autonomous Loop MCP Server
"""

import sys
import json
import uuid
import datetime
import os
import glob
import time

from bridge.config import load_config

# Load config values
config = load_config()
BRAIN_ROOT = config["brain_root"]
RESPONSES_DIR = config["responses_dir"]
INBOX_DIR = config["inbox_dir"]
INBOX_DONE_DIR = os.path.join(INBOX_DIR, "done")

AVAILABLE_MODELS = {
    "flash-low": "Gemini 3.5 Flash (Low)",
    "flash-med": "Gemini 3.5 Flash (Medium)",
    "flash-high": "Gemini 3.5 Flash (High)",
    "pro-low": "Gemini 3.1 Pro (Low)",
    "pro-high": "Gemini 3.1 Pro (High)"
}

def _find_active_conversation():
    best_id = None
    best_mtime = 0
    try:
        for entry in os.listdir(BRAIN_ROOT):
            full = os.path.join(BRAIN_ROOT, entry)
            if not os.path.isdir(full) or entry == "tempmediaStorage":
                continue
            transcript = os.path.join(full, ".system_generated", "logs", "transcript.jsonl")
            if os.path.exists(transcript):
                mtime = os.path.getmtime(transcript)
                if mtime > best_mtime:
                    best_mtime = mtime
                    best_id = entry
    except Exception:
        pass
    return best_id

def _get_paths():
    cid = _find_active_conversation()
    if not cid:
        cid = "no-active-session"
    base = os.path.join(BRAIN_ROOT, cid)
    messages = os.path.join(base, ".system_generated", "messages")
    logs = os.path.join(base, ".system_generated", "logs")
    os.makedirs(messages, exist_ok=True)
    return cid, base, messages, base, logs

def log(msg):
    print(msg, file=sys.stderr, flush=True)

def inject_message(content, title="Task from Claude Code", priority="MESSAGE_PRIORITY_HIGH"):
    cid, base_dir, messages_dir, artifacts_dir, logs_dir = _get_paths()
    log(f"Targeting active session: {cid}")
    msg_id = str(uuid.uuid4())

    # Get script paths from configuration
    gemini_side_dir = config["gemini_side_dir"]
    reply_script = os.path.join(gemini_side_dir, "reply_to_claude.py")
    send_script = os.path.join(gemini_side_dir, "send_to_claude.py")

    reply_instructions = (
        f"\n\n---\n"
        f"**[AUTONOMOUS LOOP — REPLY REQUIRED]**\n"
        f"You are operating in the autonomous Claude↔Antigravity loop.\n"
        f"When you finish this task, you MUST write your response to:\n"
        f"`{RESPONSES_DIR}/{msg_id}.txt`\n"
        f"Run: `python3 {reply_script} {msg_id} 'your response'`\n"
        f"Or write the file directly with run_command.\n"
        f"Claude Code is blocked waiting. Do NOT ask the user — just execute and reply.\n"
        f"If you want to proactively message Claude outside this task, use:\n"
        f"`python3 {send_script} 'your message'`"
    )

    payload = {
        "id": msg_id,
        "recipient": cid,
        "sender": "claude-code-bridge",
        "priority": priority,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "renderDetails": {"messageTitle": title},
        "content": content + reply_instructions
    }
    file_path = os.path.join(messages_dir, f"{msg_id}.json")
    with open(file_path, "w") as f:
        json.dump(payload, f)
    return msg_id

def handle_delegate(task, context="", model="flash-low"):
    """Delegate a task to Antigravity (fire-and-forget)."""
    lines = task.splitlines()
    for line in lines:
        if line.strip().startswith("MODEL:"):
            override = line.split("MODEL:", 1)[1].strip()
            if override in AVAILABLE_MODELS:
                model = override
            break

    model_label = AVAILABLE_MODELS.get(model, AVAILABLE_MODELS["flash-low"])

    parts = [
        "**[AUTONOMOUS LOOP]** Claude Code has delegated a task.",
        ""
    ]

    if model in AVAILABLE_MODELS:
        parts.append(f"**Requested Model**: {model_label}")
        parts.append(
            f"(Claude recommends switching to {model_label} for this task. "
            f"The user should change the model dropdown if not already set. "
            f"If you cannot change it, proceed with your current model.)"
        )
        parts.append("")

    if context:
        parts.append(f"**Context**:\n{context}\n")
    parts.append(f"**Task**:\n{task}")

    full_content = "\n".join(parts)
    msg_id = inject_message(full_content, title=f"🎯 Autonomous Task [{model_label}]")

    response_file = os.path.join(RESPONSES_DIR, f"{msg_id}.txt")

    return json.dumps({
        "status": "queued",
        "task_id": msg_id,
        "response_file": response_file
    })


def handle_check_inbox():
    """Check for proactive messages FROM Antigravity."""
    pending = sorted(glob.glob(os.path.join(INBOX_DIR, "*.json")), key=os.path.getmtime)
    messages = []
    for fpath in pending:
        try:
            with open(fpath, "r") as f:
                data = json.load(f)
            messages.append(data)
            done_path = os.path.join(INBOX_DONE_DIR, os.path.basename(fpath))
            os.rename(fpath, done_path)
        except Exception as e:
            log(f"Error reading inbox message {fpath}: {e}")

    if not messages:
        return json.dumps({"status": "empty", "messages": []})

    return json.dumps({
        "status": "has_messages",
        "count": len(messages),
        "messages": messages
    })

def handle_list_models():
    """List available Antigravity models that Claude can request."""
    return json.dumps({
        "available_models": AVAILABLE_MODELS,
        "note": (
            "Pass the model key (e.g. 'flash-low', 'pro-high') in the "
            "'model' parameter of delegate_to_antigravity. The Antigravity agent "
            "will be instructed to switch to that model. Note: the actual model "
            "switch requires the user to change the IDE dropdown — Antigravity "
            "will note the preference but cannot force-switch programmatically."
        )
    })

def handle_read_file(file_path):
    try:
        abs_path = os.path.abspath(file_path)
        with open(abs_path, "r") as f:
            content = f.read()
        return json.dumps({
            "path": abs_path,
            "content": content[:10000],
            "truncated": len(content) > 10000
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

TOOLS = [
    {
        "name": "delegate_to_antigravity",
        "description": (
            "Delegate a task to the Antigravity IDE agent (Gemini). "
            "This tool is FIRE-AND-FORGET and returns immediately with a task_id "
            "and response_file path. The caller must watch this response_file "
            "for the actual result. Use for code generation, analysis, running "
            "commands, file creation, refactoring — anything you want Antigravity to execute. "
            "You can optionally specify which model tier Antigravity should use."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Detailed task description."
                },
                "context": {
                    "type": "string",
                    "description": "Optional background context for the task."
                },
                "model": {
                    "type": "string",
                    "description": (
                        "Preferred Antigravity model tier. Options: "
                        "'flash-low' (cheapest), 'flash-med', 'flash-high', "
                        "'pro-low', 'pro-high'. Default is 'flash-low'."
                    ),
                    "enum": ["flash-low", "flash-med", "flash-high", "pro-low", "pro-high"],
                    "default": "flash-low"
                }
            },
            "required": ["task"]
        }
    },
    {
        "name": "check_antigravity_inbox",
        "description": (
            "Check for proactive messages FROM Antigravity. The Antigravity agent "
            "can send you questions, status updates, findings, or requests outside "
            "of a delegation cycle. Call this to read any pending messages. "
            "Messages are marked as read after retrieval."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "list_antigravity_models",
        "description": (
            "List available model tiers that the Antigravity IDE supports. "
            "Use this to decide which model to request for a given task."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "read_workspace_file",
        "description": "Read a file from the shared workspace filesystem.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file."
                }
            },
            "required": ["path"]
        }
    }
]

def main():
    log("🚀 Antigravity IDE Bridge MCP Server — Bidirectional Autonomous Loop")
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
                        "serverInfo": {"name": "antigravity-ide-bridge", "version": "1.0.0"}
                    }
                }
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": TOOLS}
                }
            elif method == "tools/call":
                params = req.get("params", {})
                tool_name = params.get("name", "")
                args = params.get("arguments", {})

                if tool_name == "delegate_to_antigravity":
                    result_text = handle_delegate(
                        task=args.get("task", ""),
                        context=args.get("context", ""),
                        model=args.get("model", "flash-low")
                    )
                elif tool_name == "check_antigravity_inbox":
                    result_text = handle_check_inbox()
                elif tool_name == "list_antigravity_models":
                    result_text = handle_list_models()
                elif tool_name == "read_workspace_file":
                    result_text = handle_read_file(args.get("path", ""))
                else:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                    }
                    print(json.dumps(resp), flush=True)
                    continue

                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": result_text}]
                    }
                }
            else:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not supported: {method}"}
                }
            print(json.dumps(resp), flush=True)
        except Exception as e:
            log(f"Error: {e}")
            if 'req_id' in locals() and req_id:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(e)}
                }
                print(json.dumps(resp), flush=True)

if __name__ == "__main__":
    main()
