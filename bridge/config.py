import os
import json
import sys

CONFIG_PATH = os.path.expanduser("~/.config/bridge/config.json")

DEFAULT_BRAIN_ROOTS = [
    "~/.gemini/antigravity/brain",
    "~/.gemini/antigravity-ide/brain",
    "~/.gemini/antigravity-cli/brain",
]

# Shared resolver lives on the grok_side; keep Bridge package usable even if missing
_GROK_SIDE = os.path.expanduser("~/.config/bridge/grok_side")
if _GROK_SIDE not in sys.path:
    sys.path.insert(0, _GROK_SIDE)


def load_config():
    """
    Load configuration from defaults, ~/.config/bridge/config.json, target pin, and env vars.
    """
    try:
        from bridge_target import load_config as _load

        return _load()
    except Exception:
        pass

    config = {
        "brain_root": os.path.expanduser("~/.gemini/antigravity/brain"),
        "brain_roots": [os.path.expanduser(p) for p in DEFAULT_BRAIN_ROOTS],
        "pinned_conversation_id": None,
        "pinned_conversation_title": "Grok delegations",
        "responses_dir": os.path.expanduser("~/coding-agent/bridge_responses"),
        "inbox_dir": "/tmp/bridge_to_claude",
        "gemini_side_dir": os.path.expanduser("~/.config/bridge/gemini_side"),
        "grok_responses_dir": os.path.expanduser("~/coding-agent/grok_responses"),
    }

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                user_config = json.load(f)
                for k, v in user_config.items():
                    if k == "brain_roots" and isinstance(v, list):
                        config["brain_roots"] = [os.path.expanduser(p) for p in v]
                    elif k in config and isinstance(v, str):
                        config[k] = os.path.expanduser(v) if ("/" in v or v.startswith("~")) else v
                    elif k in config:
                        config[k] = v
        except Exception:
            pass

    if "BRIDGE_RESPONSES_DIR" in os.environ:
        config["responses_dir"] = os.environ["BRIDGE_RESPONSES_DIR"]
    if "BRIDGE_INBOX_DIR" in os.environ:
        config["inbox_dir"] = os.environ["BRIDGE_INBOX_DIR"]
    if "BRIDGE_IDE_BRAIN_ROOT" in os.environ:
        config["brain_root"] = os.path.expanduser(os.environ["BRIDGE_IDE_BRAIN_ROOT"])

    os.makedirs(config["responses_dir"], exist_ok=True)
    os.makedirs(config["inbox_dir"], exist_ok=True)
    os.makedirs(os.path.join(config["inbox_dir"], "done"), exist_ok=True)
    return config
