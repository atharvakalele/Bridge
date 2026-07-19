#!/usr/bin/env bash
# install.sh — Setup script for Bridge
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Installing Bridge ==="

# 1. Create config directory
CONFIG_DIR="$HOME/.config/bridge"
echo "Creating config directory: $CONFIG_DIR"
mkdir -p "$CONFIG_DIR"

# 2. Copy Gemini side scripts
GEMINI_TARGET="$CONFIG_DIR/gemini_side"
echo "Deploying Gemini-side scripts to: $GEMINI_TARGET"
rm -rf "$GEMINI_TARGET"
cp -r "$REPO_DIR/gemini_side" "$GEMINI_TARGET"
chmod +x "$GEMINI_TARGET/waiter.sh" "$GEMINI_TARGET/reply_to_claude.py" "$GEMINI_TARGET/send_to_claude.py"

# 3. Create default config.json if not exists
CONFIG_FILE="$CONFIG_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
  echo "Creating default configuration at: $CONFIG_FILE"
  cat <<EOF > "$CONFIG_FILE"
{
  "brain_root": "~/.gemini/antigravity-ide/brain",
  "responses_dir": "/tmp/bridge_responses",
  "inbox_dir": "/tmp/bridge_to_claude",
  "gemini_side_dir": "~/.config/bridge/gemini_side"
}
EOF
else
  echo "Configuration file already exists at $CONFIG_FILE, skipping creation."
fi

# 4. Install the Python package in editable mode
echo "Installing python package via pip..."
python3 -m pip install -e "$REPO_DIR"

# 5. Print success message and registration command
echo ""
echo "✓ Installation completed successfully!"
echo "To add the MCP server to Claude Code, run:"
echo "  claude mcp add bridge-mcp-server -- bridge-mcp-server"
echo ""
echo "Or add it manually to your Claude config:"
cat <<EOF
{
  "mcpServers": {
    "bridge": {
      "command": "bridge-mcp-server"
    }
  }
}
EOF
echo ""
