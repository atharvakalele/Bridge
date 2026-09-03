#!/usr/bin/env bash
# install.sh — Setup and installer for Antigravity Bridge & agy-cli MCP
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Installing Antigravity Bridge & agy-cli MCP ==="

# 1. Create config directories
CONFIG_DIR="$HOME/.config/bridge"
echo "Creating config directories under: $CONFIG_DIR"
mkdir -p "$CONFIG_DIR/agy_cli" "$CONFIG_DIR/gemini_side" "$CONFIG_DIR/grok_side"

# 2. Deploy agy_cli, gemini-side and grok-side scripts
echo "Deploying bridge scripts to: $CONFIG_DIR"
cp -r "$REPO_DIR/agy_cli/"* "$CONFIG_DIR/agy_cli/" 2>/dev/null || true
cp -r "$REPO_DIR/gemini_side/"* "$CONFIG_DIR/gemini_side/" 2>/dev/null || true
cp -r "$REPO_DIR/grok_side/"* "$CONFIG_DIR/grok_side/" 2>/dev/null || true
chmod +x "$CONFIG_DIR/agy_cli/"*.py 2>/dev/null || true
chmod +x "$CONFIG_DIR/gemini_side/"*.sh "$CONFIG_DIR/gemini_side/"*.py 2>/dev/null || true
chmod +x "$CONFIG_DIR/grok_side/"*.sh "$CONFIG_DIR/grok_side/"*.py 2>/dev/null || true

# 3. Create default config.json only if not present (never overwrite user config blindly)
CONFIG_FILE="$CONFIG_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
  echo "Creating default configuration at: $CONFIG_FILE"
  cat <<'EOF' > "$CONFIG_FILE"
{
  "brain_root": "~/.gemini/antigravity-cli/brain",
  "brain_roots": [
    "~/.gemini/antigravity-cli/brain",
    "~/.gemini/antigravity/brain",
    "~/.gemini/antigravity-ide/brain"
  ],
  "pinned_conversation_title": "Grok delegations",
  "responses_dir": "~/coding-agent/bridge_responses",
  "grok_responses_dir": "~/coding-agent/grok_responses",
  "inbox_dir": "/tmp/bridge_to_claude",
  "gemini_side_dir": "~/.config/bridge/gemini_side"
}
EOF
else
  echo "Existing configuration found at $CONFIG_FILE (preserving)."
fi

# 4. Install python package in editable mode
echo "Installing Python package in editable mode..."
python3 -m pip install -e "$REPO_DIR"

# 5. Symlink CLI helpers to ~/.local/bin if available
if [ -d "$HOME/.local/bin" ]; then
  echo "Ensuring helper scripts in ~/.local/bin..."
  ln -sf "$REPO_DIR/scripts/agy-cli-mcp" "$HOME/.local/bin/agy-cli-mcp"
  ln -sf "$REPO_DIR/scripts/agy-job" "$HOME/.local/bin/agy-job"
  ln -sf "$REPO_DIR/scripts/agy-prune" "$HOME/.local/bin/agy-prune"
fi

# 6. Auto-detect and register MCP for installed agent CLIs
echo ""
echo "=== MCP Registration Check ==="

if command -v claude >/dev/null 2>&1; then
  echo "Found Claude CLI. Registering agy-cli MCP..."
  claude mcp add agy-cli -- agy-cli-mcp 2>/dev/null || echo "  (Claude MCP registration command ready: claude mcp add agy-cli -- agy-cli-mcp)"
else
  echo "Claude CLI not found on PATH. To register manually in Claude:"
  echo "  claude mcp add agy-cli -- agy-cli-mcp"
fi

if command -v grok >/dev/null 2>&1; then
  echo "Found Grok CLI. Registering agy-cli MCP..."
  grok mcp add agy-cli -- agy-cli-mcp 2>/dev/null || echo "  (Grok MCP registration: grok mcp add agy-cli -- agy-cli-mcp)"
else
  echo "Grok CLI not found on PATH. To register in Grok, add to config or run:"
  echo "  grok mcp add agy-cli -- agy-cli-mcp"
fi

echo ""
echo "For Cline / VS Code: copy templates/agy-cli.cline.json into cline_mcp_settings.json"
echo ""
echo "✓ Installation completed successfully!"
echo "Test the CLI worker: agy-job "echo 'Hello from Antigravity'""
