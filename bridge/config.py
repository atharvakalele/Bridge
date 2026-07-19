import os
import json

CONFIG_PATH = os.path.expanduser("~/.config/bridge/config.json")

def load_config():
    """
    Load configuration from defaults, ~/.config/bridge/config.json, and env vars.
    Returns a dict containing:
      - brain_root: Path to the Antigravity IDE brain directory
      - responses_dir: Path where Gemini writes task responses
      - inbox_dir: Path where Gemini writes proactive inbox messages
      - gemini_side_dir: Path where gemini-side script templates/files live
    """
    config = {
        "brain_root": os.path.expanduser("~/.gemini/antigravity-ide/brain"),
        "responses_dir": "/tmp/bridge_responses",
        "inbox_dir": "/tmp/bridge_to_claude",
        "gemini_side_dir": os.path.expanduser("~/.config/bridge/gemini_side")
    }

    # Load from config.json if exists
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                user_config = json.load(f)
                for k, v in user_config.items():
                    if k in config:
                        config[k] = os.path.expanduser(v) if isinstance(v, str) else v
        except Exception:
            pass

    # Env var overrides
    if "BRIDGE_TMP_DIR" in os.environ:
        tmp_base = os.environ["BRIDGE_TMP_DIR"]
        config["responses_dir"] = os.path.join(tmp_base, "responses")
        config["inbox_dir"] = os.path.join(tmp_base, "to_claude")

    if "BRIDGE_RESPONSES_DIR" in os.environ:
        config["responses_dir"] = os.environ["BRIDGE_RESPONSES_DIR"]

    if "BRIDGE_INBOX_DIR" in os.environ:
        config["inbox_dir"] = os.environ["BRIDGE_INBOX_DIR"]

    if "BRIDGE_IDE_BRAIN_ROOT" in os.environ:
        config["brain_root"] = os.path.expanduser(os.environ["BRIDGE_IDE_BRAIN_ROOT"])

    if "BRIDGE_GEMINI_SIDE_DIR" in os.environ:
        config["gemini_side_dir"] = os.path.expanduser(os.environ["BRIDGE_GEMINI_SIDE_DIR"])

    # Ensure directories exist
    os.makedirs(config["responses_dir"], exist_ok=True)
    os.makedirs(config["inbox_dir"], exist_ok=True)
    os.makedirs(os.path.join(config["inbox_dir"], "done"), exist_ok=True)

    return config
