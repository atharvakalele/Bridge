# Antigravity Bridge

> Delegate heavy coding tasks from **Grok Build**, **Claude Code**, or **Cline** directly to **Google Antigravity CLI** (`agy`) via MCP — powered by your Google Gemini subscription, not per-token API fees.

---

## ⚡ What This Is

Antigravity Bridge enables orchestrator agents (Grok, Claude Code, Cline) to treat **Antigravity CLI** as an autonomous sub-worker through the Model Context Protocol (MCP).

When an agent needs to explore a massive codebase, execute refactors, run test suites, or edit dozens of files:
1. The parent agent invokes `agy_run` with a task prompt.
2. `agy_run` is **fire-and-forget**: it starts a detached job supervisor and returns immediately with a `job_id` (so Grok/Claude is never blocked or timing out during tool execution).
3. The supervisor launches official `agy -p` in stream-json mode, opens/reuses a single visible preview terminal titled `AG-job`, and writes logs and completion status.
4. The parent monitors completion by running `watch_job.py <job_id>` or checking `notify` / `agy_status`.

---

## 🚀 Key Architectural Details

- **Fire-and-Forget Job Supervisor**: `agy_run` returns immediately. The detached supervisor manages `agy -p`, tees output to `job.log` and `stream.ndjson`, and writes classified results (`SUCCESS`, `ERROR`, `CRASH`, `TIMEOUT`, `NETWORK`, `CANCELED`).
- **Single Preview Window**: Opens or reuses one visible preview window titled `AG-job` (`xfce4-terminal --disable-server`). Existing preview windows are reused instead of stacking new ones. Closing the preview window does **not** kill Antigravity. Window management carefully avoids touching Grok's own terminal panes.
- **Per-CWD Conversation Sessions**: Maintains a mapping between repository `cwd` and Antigravity conversation IDs. Follow-up jobs in the same working directory automatically continue the existing AG conversation context unless `new_session=true` is requested.
- **Concurrency Protection**: Returns `ALREADY_RUNNING` if a job is already in flight to avoid colliding processes.
- **Gemini Subscription Powered**: Runs on your authenticated Google / Gemini subscription via official `agy` without per-token API billing.
- **Sensible, Safe Model Defaults**: Defaults to `gemini-3.7-flash-medium`. Quota-heavy models (e.g. Claude Opus) are blocked to prevent quota exhaustion.

---

## ⚠️ Honest Limitations & Current Status

- **Still in Active Development**: Edge cases across `TIMEOUT`, `CRASH`, and `NETWORK` recovery paths, multi-job queuing, and in-session MCP hot-reloading are not yet fully proven under all scenarios.
- **Headless CLI Execution**: Detached jobs expect tasks to complete and exit cleanly. The runner extracts `result` stream events and manages clean process shutdown.
- **Legacy GUI Mode**: The `bridge-mcp-server` / `waiter.sh` file-spool workflow for the Antigravity IDE GUI remains available as legacy, while `agy-cli` is the modern CLI path.
- **Official CLI Required**: Requires an authenticated local installation of Google Antigravity CLI (`agy`).

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
| `agy_run` | `task` (required), `cwd`, `model`, `timeout`, `continue_last`, `conversation_id`, `new_session` | Detached fire-and-forget execution. Spawns supervisor, opens preview terminal, returns `job_id` immediately. |
| `agy_models` | *none* | Lists available model slugs on the authenticated account. |
| `agy_status` | `job_id` (optional) | Returns metadata and state from the specified or last run (`finish`, `status`, `cwd`, `model`, `log`). |

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
