#!/usr/bin/env python3
import sys
import os
import json

def load_config():
    config_path = os.path.expanduser("~/.config/bridge/config.json")
    config = {
        "grok_responses_dir": os.path.expanduser("~/coding-agent/grok_responses")
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                user_config = json.load(f)
                if "grok_responses_dir" in user_config:
                    config["grok_responses_dir"] = os.path.expanduser(user_config["grok_responses_dir"])
        except Exception:
            pass

    if "GROK_RESPONSES_DIR" in os.environ:
        config["grok_responses_dir"] = os.environ["GROK_RESPONSES_DIR"]

    return config

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 reply_to_grok.py <message_id> <response text...>")
        sys.exit(1)

    msg_id = sys.argv[1]
    response_text = " ".join(sys.argv[2:])

    config = load_config()
    responses_dir = config["grok_responses_dir"]
    os.makedirs(responses_dir, exist_ok=True)

    resp_file = os.path.join(responses_dir, f"{msg_id}.txt")
    with open(resp_file, "w") as f:
        f.write(response_text)

    # Write to /tmp/grok_responses as fallback
    fallback_dir = "/tmp/grok_responses"
    os.makedirs(fallback_dir, exist_ok=True)
    fallback_file = os.path.join(fallback_dir, f"{msg_id}.txt")
    with open(fallback_file, "w") as f:
        f.write(response_text)

    print(f"✅ Response sent to Grok. Written to {resp_file} and {fallback_file}")

if __name__ == "__main__":
    main()
