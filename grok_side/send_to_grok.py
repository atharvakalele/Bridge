#!/usr/bin/env python3
"""
send_to_grok.py — Antigravity → Grok message sender

Drops a JSON message into the Grok bridge inbox directory.

Usage:
    python3 send_to_grok.py "Your message to Grok"
"""

import datetime
import json
import os
import sys
import uuid


def load_config():
    config_path = os.path.expanduser("~/.config/bridge/config.json")
    config = {
        "grok_inbox_dir": "/tmp/bridge_to_grok"
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                user_config = json.load(f)
                if "grok_inbox_dir" in user_config:
                    config["grok_inbox_dir"] = os.path.expanduser(user_config["grok_inbox_dir"])
        except Exception:
            pass
    return config


def send_to_grok(message):
    config = load_config()
    inbox_dir = config["grok_inbox_dir"]
    os.makedirs(inbox_dir, exist_ok=True)

    msg_id = str(uuid.uuid4())
    payload = {
        "id": msg_id,
        "sender": "antigravity",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "content": message,
    }
    file_path = os.path.join(inbox_dir, f"{msg_id}.json")
    with open(file_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"✅ Message queued for Grok: {file_path}")
    return msg_id


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 send_to_grok.py 'Your message here'")
        sys.exit(1)

    message = " ".join(sys.argv[1:])
    msg_id = send_to_grok(message)
    print(f"   Message ID: {msg_id}")
