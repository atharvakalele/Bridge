#!/usr/bin/env bash
# Install this checkout so Grok/Claude/Cline match the published worker + skill.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_DIR="${HOME}/.config/bridge"
BIN_DIR="${HOME}/.local/bin"
GROK_SKILL="${HOME}/.grok/skills/agy-cli"

echo "Installing Bridge from ${REPO_DIR}"

mkdir -p "$CONFIG_DIR/agy_cli" "$CONFIG_DIR/gemini_side" "$CONFIG_DIR/grok_side" "$BIN_DIR" "$GROK_SKILL"

cp -a "$REPO_DIR/agy_cli/." "$CONFIG_DIR/agy_cli/"
if [[ -d "$REPO_DIR/gemini_side" ]]; then
  cp -a "$REPO_DIR/gemini_side/." "$CONFIG_DIR/gemini_side/"
fi
if [[ -d "$REPO_DIR/grok_side" ]]; then
  cp -a "$REPO_DIR/grok_side/." "$CONFIG_DIR/grok_side/"
fi
cp -a "$REPO_DIR/skills/agy-cli/." "$GROK_SKILL/"

chmod +x "$CONFIG_DIR/agy_cli/"*.py 2>/dev/null || true

# Claude always-on rules (replace only the snippet file we own; write CLAUDE.md if missing)
if [[ -f "$REPO_DIR/templates/CLAUDE.md.snippet" ]]; then
  if [[ ! -f "${HOME}/.claude/CLAUDE.md" ]]; then
    mkdir -p "${HOME}/.claude"
    cp "$REPO_DIR/templates/CLAUDE.md.snippet" "${HOME}/.claude/CLAUDE.md"
  else
    cp "$REPO_DIR/templates/CLAUDE.md.snippet" "${HOME}/.claude/CLAUDE.md"
  fi
fi

CONFIG_FILE="$CONFIG_DIR/config.json"
if [[ ! -f "$CONFIG_FILE" ]]; then
  cat >"$CONFIG_FILE" <<'EOF'
{
  "note": "Local paths. Created by scripts/install.sh. Do not commit."
}
EOF
fi

ln -sfn "$REPO_DIR/scripts/agy-cli-mcp" "$BIN_DIR/agy-cli-mcp"
ln -sfn "$REPO_DIR/scripts/agy-job" "$BIN_DIR/agy-job"
ln -sfn "$REPO_DIR/scripts/agy-prune" "$BIN_DIR/agy-prune"
chmod +x "$REPO_DIR/scripts/agy-cli-mcp" "$REPO_DIR/scripts/agy-job" "$REPO_DIR/scripts/agy-prune" "$REPO_DIR/scripts/sync-agy-cli.sh"

if command -v grok >/dev/null 2>&1; then
  grok mcp add --scope user agy-cli "$BIN_DIR/agy-cli-mcp" 2>/dev/null || true
  echo "Grok MCP: agy-cli -> $BIN_DIR/agy-cli-mcp"
else
  echo "grok CLI not on PATH; add MCP later: grok mcp add --scope user agy-cli $BIN_DIR/agy-cli-mcp"
fi

if command -v claude >/dev/null 2>&1; then
  claude mcp add --scope user agy-cli "$BIN_DIR/agy-cli-mcp" 2>/dev/null || true
  echo "Claude MCP: agy-cli -> $BIN_DIR/agy-cli-mcp"
else
  echo "claude CLI not on PATH; add MCP later: claude mcp add --scope user agy-cli $BIN_DIR/agy-cli-mcp"
fi

if [[ -f "$REPO_DIR/scripts/sync-agy-cli.sh" ]]; then
  bash "$REPO_DIR/scripts/sync-agy-cli.sh" --check || true
fi

# AG CLI instructions (so agy -p does not start waiter.sh)
mkdir -p "${HOME}/.gemini/antigravity-cli"
if [[ -f "$REPO_DIR/templates/GEMINI.md" ]]; then
  cp "$REPO_DIR/templates/GEMINI.md" "${HOME}/.gemini/GEMINI.md"
fi
if [[ -f "$REPO_DIR/templates/AGENTS.md" ]]; then
  cp "$REPO_DIR/templates/AGENTS.md" "${HOME}/.gemini/antigravity-cli/AGENTS.md"
fi

echo
echo "Installed."
echo "  worker:  $CONFIG_DIR/agy_cli"
echo "  skill:   $GROK_SKILL/SKILL.md"
echo "  grok:    $CONFIG_DIR/grok_side/GROK_SYSTEM_PROMPT.md"
echo "Restart Grok / Claude / Cline so they load MCP + skill."
echo "Clone is not enough by itself — this script is what matches our running state."
