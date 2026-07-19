#!/usr/bin/env bash
# start_bridge.sh — Helper script to verify installation and print status
set -euo pipefail

CONFIG_FILE="$HOME/.config/bridge/config.json"

echo "=== Bridge Status & Verification ==="
echo ""

# 1. Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
  echo "❌ Configuration file not found at: $CONFIG_FILE"
  echo "Please run install.sh first."
  exit 1
fi
echo "✓ Config file found: $CONFIG_FILE"

# 2. Parse config file paths
BRAIN_ROOT=$(python3 -c "import json, os; print(os.path.expanduser(json.load(open('$CONFIG_FILE'))['brain_root']))")
RESPONSES_DIR=$(python3 -c "import json, os; print(os.path.expanduser(json.load(open('$CONFIG_FILE'))['responses_dir']))")
INBOX_DIR=$(python3 -c "import json, os; print(os.path.expanduser(json.load(open('$CONFIG_FILE'))['inbox_dir']))")
GEMINI_SIDE_DIR=$(python3 -c "import json, os; print(os.path.expanduser(json.load(open('$CONFIG_FILE'))['gemini_side_dir']))")

echo "  - Brain Root: $BRAIN_ROOT"
echo "  - Responses Directory: $RESPONSES_DIR"
echo "  - Inbox Directory: $INBOX_DIR"
echo "  - Gemini-side Scripts: $GEMINI_SIDE_DIR"
echo ""

# 3. Verify communication directories exist
for dir in "$BRAIN_ROOT" "$RESPONSES_DIR" "$INBOX_DIR" "$GEMINI_SIDE_DIR"; do
  if [ -d "$dir" ]; then
    echo "✓ Directory exists: $dir"
  else
    echo "⚠️  Directory does not exist: $dir (will be auto-created when running or can be created manually)"
  fi
done
echo ""

# 4. Check for console script command
if command -v bridge-mcp-server &>/dev/null; then
  echo "✓ bridge-mcp-server command is registered in path: $(command -v bridge-mcp-server)"
else
  echo "⚠️  bridge-mcp-server command not found in PATH."
  echo "Make sure you installed with 'pip install -e .' in your active python environment."
fi
echo ""

# 5. Check Claude MCP registrations
CLAUDE_CONFIG="$HOME/.claude.json"
CLAUDE_CONFIG_DIR_JSON="$HOME/.config/Claude/mcp.json"
REGISTERED=false

check_mcp_config() {
  local cfg="$1"
  if [ -f "$cfg" ] && grep -q "bridge-mcp-server\|bridge" "$cfg"; then
    echo "✓ Registered in Claude Code config: $cfg"
    REGISTERED=true
  fi
}

check_mcp_config "$CLAUDE_CONFIG"
check_mcp_config "$CLAUDE_CONFIG_DIR_JSON"

if [ "$REGISTERED" = false ]; then
  echo "⚠️  Could not confirm registration in Claude Code configurations (~/.claude.json or ~/.config/Claude/mcp.json)."
  echo "Register it with: claude mcp add bridge-mcp-server -- bridge-mcp-server"
fi

echo ""
echo "=== Setup verification complete ==="
