# Installing Antigravity Bridge

Follow these steps to set up Antigravity delegation for **Grok Build**, **Claude Code**, and **Cline**.

---

## 1. Prerequisites

- **Python 3.8+**
- **Official Google Antigravity CLI (`agy`)**:
  Make sure `agy` is installed and authenticated:
  ```bash
  agy auth login
  ```
- Any orchestrator agent CLI: `grok`, `claude`, or VS Code with `cline`.

---

## 2. Installation

From the root of this repository:

```bash
# 1. Install package in editable mode
pip install -e .

# 2. Run the setup installer
bash scripts/install.sh
```

The installer will:
- Create configuration folders in `~/.config/bridge/`
- Set up default non-destructive configuration if `~/.config/bridge/config.json` doesn't exist
- Symlink CLI helper scripts (`agy-cli-mcp`, `agy-job`, `agy-prune`) into `~/.local/bin`
- Attempt auto-registration for detected agent CLIs

---

## 3. MCP Registration

### Option A: `agy-cli` (Recommended for Grok, Claude Code, Cline)

- **Grok**:
  ```bash
  grok mcp add agy-cli -- agy-cli-mcp
  ```
- **Claude Code**:
  ```bash
  claude mcp add agy-cli -- agy-cli-mcp
  ```
- **Cline (VS Code)**:
  Add configuration from `templates/agy-cli.cline.json` into `cline_mcp_settings.json`.

### Option B: `bridge-mcp-server` (Legacy GUI Inbox Mode)

If using the older fire-and-forget loop with an interactive Antigravity IDE GUI chat running `waiter.sh`:

- **Claude Code**:
  ```bash
  claude mcp add bridge-mcp-server -- bridge-mcp-server
  ```
- Configure IDE agent rules from `gemini_side/AGENT_RULES.md`.

---

## 4. Verification

Verify the MCP worker:
```bash
agy-job --timeout 2m "echo 'Hello from Antigravity worker'"
```
