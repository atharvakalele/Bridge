# Antigravity Bridge

> Delegate heavy coding tasks from **Grok Build**, **Claude Code**, or **Cline** directly to **Google Antigravity CLI** (`agy`) via MCP — powered by your Google Gemini subscription, not per-token API fees.

---

## ⚡ What This Is

Antigravity Bridge enables orchestrator agents (Grok, Claude Code, Cline) to treat **Antigravity CLI** as an autonomous, high-throughput sub-worker through the Model Context Protocol (MCP).

When an agent needs to explore a massive codebase, execute refactors, run test suites, or edit dozens of files:
1. The parent agent invokes `agy_run` with a task prompt.
2. The MCP server spawns the official `agy` CLI as a child process in headless print mode (`agy -p`).
3. Antigravity executes autonomously with tool access (file search, edits, shell execution).
4. The parent receives structured JSON (`status`, `conversation_id`, `response`) upon completion.

---

## 🚀 What Wonders It Does

- **Saves Parent Tokens & Context**: Stop stuffing 50 files into Claude or Grok context windows. Antigravity does the local exploration, analysis, and implementation, returning only the summary and results.
- **Powered by Gemini Subscription**: Runs on your authenticated Google / Gemini subscription via `agy` (no separate OpenAI/Anthropic API bills for sub-tasks).
- **Automated Conversation Lifecycle**: Conversation IDs are tracked in state. Follow up in the same session using `continue_last=true` or pass a specific `conversation_id`.
- **Sensible, Safe Defaults**: Defaults to `gemini-3.7-flash-medium` for blazing speed and high throughput. Quota-heavy models (like Claude Opus) are strictly blocked to prevent accidental exhaustion.

---

## ⚠️ Honest Limitations

- **Not Stress-Tested**: This bridge is under active development and built for rapid local workflows. Edge-case error handling and retries are evolving.
- **No Background Daemons in Headless Mode**: Headless `agy -p` expects tasks to complete and exit cleanly. If Antigravity starts a long-running background daemon or tracking loop, the process can hang until timeout.
- **Official CLI Required**: You must install the official Google Antigravity CLI (`agy`) and authenticate before running this MCP server.
- **Two Distinct Modes**:
  - **`agy-cli` (New / Default)**: Direct child-process execution per tool call (`agy_run`). No GUI or waiter loop needed.
  - **`bridge-mcp-server` (Legacy GUI Inbox)**: Asynchronous file-spool bridge that communicates with an open Antigravity IDE window running `waiter.sh`.

---

## 🛠️ Quickstart & Local Installation

### 1. Prerequisites
Install the official Antigravity CLI and sign in:
```bash
# Follow official Google Antigravity installation (e.g. installer script)
agy auth login
```

Verify your CLI works:
```bash
agy --version
agy models
```

### 2. Clone & Install
```bash
git clone git@github.com:atharvakalele/Bridge.git
cd Bridge

# Install package in editable mode
pip install -e .

# Run installer (sets up config and symlinks helper scripts)
./scripts/install.sh
```

---

## 🔌 Registering the MCP Server

### Grok Build / Grok CLI
Run via CLI:
```bash
grok mcp add agy-cli -- agy-cli-mcp
```
Or add the snippet from `templates/agy-cli.grok.toml` into your Grok configuration:
```toml
[mcp_servers.agy_cli]
command = "agy-cli-mcp"
```

### Claude Code
Run via CLI:
```bash
claude mcp add agy-cli -- agy-cli-mcp
```
Or add to `~/.claude/claude_desktop_config.json` (see `templates/agy-cli.claude.json`):
```json
{
  "mcpServers": {
    "agy-cli": {
      "command": "agy-cli-mcp"
    }
  }
}
```

### Cline (VS Code Extension)
Add `agy-cli` to your `cline_mcp_settings.json` (see `templates/agy-cli.cline.json`):
```json
{
  "mcpServers": {
    "agy-cli": {
      "command": "agy-cli-mcp",
      "args": [],
      "disabled": false,
      "autoApprove": [
        "agy_run",
        "agy_models",
        "agy_status"
      ]
    }
  }
}
```
*(No API keys or passwords required.)*

---

## 🧰 MCP Tools & CLI Helpers

### MCP Tools exposed by `agy-cli`

| Tool | Parameters | Description |
|---|---|---|
| `agy_run` | `task` (required), `cwd`, `model`, `timeout`, `continue_last`, `conversation_id` | Spawns `agy -p`, executes the task, blocks until completion, and returns JSON result. |
| `agy_models` | *none* | Lists available model slugs on the authenticated account. |
| `agy_status` | *none* | Returns metadata and state from the last run (`conversation_id`, `status`, `cwd`, `model`). |

### CLI Utilities

- **`agy-job`**: Execute delegations directly from your shell or parent scripts:
  ```bash
  agy-job --cwd /path/to/project --timeout 10m "Refactor auth middleware and add unit tests"
  ```
- **`agy-prune`**: Clean up stale conversation databases and transcript artifacts:
  ```bash
  agy-prune          # Prunes all past runs except the last successful conversation
  agy-prune --all    # Cleans all CLI conversation artifacts
  ```

---

## 🌿 Branch Policy & Contributing

- **`main`**: Stable, tagged release snapshots.
- **`dev`**: Default active development branch. All Pull Requests should target `dev`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines, testing instructions, and pull request conventions.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
