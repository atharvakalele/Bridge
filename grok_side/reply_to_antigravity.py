#!/usr/bin/env python3
"""
reply_to_antigravity.py — Grok → Antigravity response writer

Usage:
    python3 reply_to_antigravity.py <message_id> <response text...>
"""

import json
import os
import sys


def load_config():
    config_path = os.path.expanduser("~/.config/bridge/config.json")
    config = {
        "responses_dir": os.path.expanduser("~/coding-agent/bridge_responses")
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                user_config = json.load(f)
                if "responses_dir" in user_config:
                    config["responses_dir"] = os.path.expanduser(user_config["responses_dir"])
        except Exception:
            pass
    return config


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 reply_to_antigravity.py <message_id> <response text...>")
        sys.exit(1)

    msg_id = sys.argv[1]
    response_text = " ".join(sys.argv[2:])

    config = load_config()
    responses_dir = config["responses_dir"]
    os.makedirs(responses_dir, exist_ok=True)

    resp_file = os.path.join(responses_dir, f"{msg_id}.txt")
    with open(resp_file, "w") as f:
        f.write(response_text)

    fallback_dir = "/tmp/bridge_responses"
    os.makedirs(fallback_dir, exist_ok=True)
    fallback_file = os.path.join(fallback_dir, f"{msg_id}.txt")
    with open(fallback_file, "w") as f:
        f.write(response_text)

    print(f"✅ Response sent to Antigravity. Written to {resp_file} and {fallback_file}")


if __name__ == "__main__":
    main()
