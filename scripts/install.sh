#!/usr/bin/env bash
# Install Grok ↔ Antigravity CLI only. Does not touch Cline or Claude MCP.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_DIR="${HOME}/.config/bridge"
BIN_DIR="${HOME}/.local/bin"
GROK_SKILL="${HOME}/.grok/skills/agy-cli"

echo "Installing Grok-AG worker from ${REPO_DIR}"

mkdir -p "$CONFIG_DIR/agy_cli" "$CONFIG_DIR/grok_side" "$BIN_DIR" "$GROK_SKILL"

cp -a "$REPO_DIR/agy_cli/." "$CONFIG_DIR/agy_cli/"
if [[ -d "$REPO_DIR/grok_side" ]]; then
  cp -a "$REPO_DIR/grok_side/." "$CONFIG_DIR/grok_side/"
fi
cp -a "$REPO_DIR/skills/agy-cli/." "$GROK_SKILL/"
chmod +x "$CONFIG_DIR/agy_cli/"*.py 2>/dev/null || true

ln -sfn "$REPO_DIR/scripts/agy-cli-mcp" "$BIN_DIR/agy-cli-mcp"
chmod +x "$REPO_DIR/scripts/agy-cli-mcp" "$REPO_DIR/scripts/sync-agy-cli.sh"

mkdir -p "${HOME}/.gemini/antigravity-cli"
if [[ -f "$REPO_DIR/templates/GEMINI.md" ]]; then
  cp "$REPO_DIR/templates/GEMINI.md" "${HOME}/.gemini/GEMINI.md"
fi
if [[ -f "$REPO_DIR/templates/AGENTS.md" ]]; then
  cp "$REPO_DIR/templates/AGENTS.md" "${HOME}/.gemini/antigravity-cli/AGENTS.md"
fi

if command -v grok >/dev/null 2>&1; then
  grok mcp add --scope user agy-cli "$BIN_DIR/agy-cli-mcp" 2>/dev/null || true
  echo "Grok MCP: agy-cli -> $BIN_DIR/agy-cli-mcp"
else
  echo "grok CLI not on PATH; later: grok mcp add --scope user agy-cli $BIN_DIR/agy-cli-mcp"
fi

if [[ -f "$REPO_DIR/scripts/sync-agy-cli.sh" ]]; then
  bash "$REPO_DIR/scripts/sync-agy-cli.sh" --check || true
fi

echo
echo "Grok-AG only. Cline and Claude MCP were not changed."
echo "  worker: $CONFIG_DIR/agy_cli"
echo "  skill:  $GROK_SKILL/SKILL.md"
echo "Start Grok with grok-ide, then restart the chat so MCP loads."
