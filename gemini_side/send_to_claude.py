#!/usr/bin/env python3
"""
send_to_claude.py — Antigravity → Claude Code message sender

Drops a JSON message into the bridge inbox directory which Claude Code reads
via the check_antigravity_inbox MCP tool. No API calls, no stdin injection.

Usage:
    python3 send_to_claude.py "Your message to Claude Code"
"""

import sys
import os
import json
import uuid
import datetime

def load_config():
    config_path = os.path.expanduser("~/.config/bridge/config.json")
    config = {
        "responses_dir": "/tmp/bridge_responses",
        "inbox_dir": "/tmp/bridge_to_claude"
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                user_config = json.load(f)
                for k in ["responses_dir", "inbox_dir"]:
                    if k in user_config:
                        config[k] = os.path.expanduser(user_config[k])
        except Exception:
            pass

    if "BRIDGE_TMP_DIR" in os.environ:
        tmp_base = os.environ["BRIDGE_TMP_DIR"]
        config["responses_dir"] = os.path.join(tmp_base, "responses")
        config["inbox_dir"] = os.path.join(tmp_base, "to_claude")

    if "BRIDGE_RESPONSES_DIR" in os.environ:
        config["responses_dir"] = os.environ["BRIDGE_RESPONSES_DIR"]

    if "BRIDGE_INBOX_DIR" in os.environ:
        config["inbox_dir"] = os.environ["BRIDGE_INBOX_DIR"]

    return config

def send_to_claude(message):
    config = load_config()
    inbox_dir = config["inbox_dir"]
    os.makedirs(inbox_dir, exist_ok=True)

    msg_id = str(uuid.uuid4())
    payload = {
        "id": msg_id,
        "sender": "antigravity",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "content": message
    }
    file_path = os.path.join(inbox_dir, f"{msg_id}.json")
    with open(file_path, "w") as f:
        json.dump(payload, f)
    print(f"✅ Message queued for Claude Code: {file_path}")
    return msg_id

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 send_to_claude.py 'Your message here'")
        sys.exit(1)

    message = " ".join(sys.argv[1:])
    msg_id = send_to_claude(message)
    print(f"   Message ID: {msg_id}")
    print(f"   Claude Code will see it when it calls check_antigravity_inbox")
