#!/usr/bin/env python3
import sys
import os
import json

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

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 reply_to_claude.py <message_id> <response text...>")
        sys.exit(1)

    msg_id = sys.argv[1]
    response_text = " ".join(sys.argv[2:])

    config = load_config()
    responses_dir = config["responses_dir"]
    os.makedirs(responses_dir, exist_ok=True)

    resp_file = os.path.join(responses_dir, f"{msg_id}.txt")
    with open(resp_file, "w") as f:
        f.write(response_text)

    print(f"✅ Response sent to Claude Code. Written to {resp_file}")

if __name__ == "__main__":
    main()
