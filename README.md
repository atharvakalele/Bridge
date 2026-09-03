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
- **FIFO Job Queue**: If a job is already in flight, new requests are queued (`status=QUEUED`) via flock-synchronized `queue.json`. When the active job completes, the supervisor automatically starts the next queued job in FIFO order.
- **Single Preview Window & Reopen**: Opens or reuses one visible preview window titled `AG-job` (`xfce4-terminal --disable-server`). Logs stay open upon completion so history remains visible. If the preview pane is closed while a job is running, `preview_closed=true` is recorded and can be queried or restored via `agy_preview`. Window management never touches Grok's terminal panes.
- **Wall-Clock Timeout Enforcement**: The supervisor calculates strict wall-clock deadlines from timeout strings (`15m`, `60s`, `2h`) and terminates the process if the time limit is exceeded, recording `finish=TIMEOUT`.
- **Per-CWD Conversation Sessions**: Maintains a mapping between repository `cwd` and Antigravity conversation IDs. Follow-up jobs in the same working directory automatically continue the existing AG conversation context unless `new_session=true` is requested.
- **Gemini Subscription Powered**: Runs on your authenticated Google / Gemini subscription via official `agy` without per-token API billing.
- **Sensible, Safe Model Defaults**: Defaults to `gemini-3.7-flash-medium`. Quota-heavy models (e.g. Claude Opus) are blocked to prevent quota exhaustion.

---

## 📊 Finish Classifications (Plain English)

Every job execution completes with one of the following classified finish kinds:

- **`SUCCESS`**: Task completed successfully with result status SUCCESS.
- **`ERROR`**: Antigravity reported an error during task execution.
- **`CRASH`**: The agy process died or exited without emitting a final result event.
- **`TIMEOUT`**: Execution hit the wall-clock timeout limit and was stopped by the supervisor.
- **`NETWORK`**: Network, authentication, rate limit (429), or server error (5xx) occurred.
- **`CANCELED`**: Job was canceled or interrupted before completion.

---

## ⚠️ Current Status & Robustness

- **Queue & Timeout Support**: Multi-job queuing, live preview-closed detection, and wall-clock timeout enforcement exist and will be stress-tested before the next push.
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

A git clone is the source tree. It is **not** a running Grok/Claude session. To match the state we run here (worker + MCP + skill + rules):

```bash
git clone git@github.com:atharvakalele/Bridge.git
cd Bridge
./scripts/install.sh
```

That script:

- copies `agy_cli/` to `~/.config/bridge/agy_cli/` (the live worker)
- installs the Grok skill to `~/.grok/skills/agy-cli/SKILL.md`
- copies Grok rules to `~/.config/bridge/grok_side/GROK_SYSTEM_PROMPT.md`
- writes Claude rules to `~/.claude/CLAUDE.md`
- registers user-scoped MCP `agy-cli` for Grok and Claude if those CLIs exist
- symlinks `agy-cli-mcp` into `~/.local/bin`

Then **restart** Grok / Claude / Cline. Forks and clones that skip `install.sh` will not have the skill or MCP.

Work on `dev`; `main` is the default GitHub branch.

### 3. Syncing Worker Code
To synchronize or verify Python worker code between the repository and your live config (`~/.config/bridge/agy_cli/`):
```bash
# Install / sync repository files to live directory
./scripts/sync-agy-cli.sh

# Verify no drift exists (exits 1 if drift detected)
./scripts/sync-agy-cli.sh --check
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
        "agy_status",
        "agy_preview"
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
| `agy_run` | `task` (required), `cwd`, `model`, `timeout`, `continue_last`, `conversation_id`, `new_session` | Detached fire-and-forget execution. Spawns supervisor (or queues behind active jobs), opens preview terminal, returns `job_id` immediately. |
| `agy_models` | *none* | Lists available model slugs on the authenticated account. |
| `agy_status` | `job_id` (optional) | Returns metadata and state from the specified or last run (`finish`, `status`, `cwd`, `model`, `log`, `preview_open`). |
| `agy_preview` | `action` (`status` \| `reopen` \| `hide`), `job_id` (optional) | Inspects preview window status, reopens a closed preview terminal, or hides/dismisses the pane. |

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

- **`main`**: Default branch and stable release snapshots (`master` has been removed).
- **`dev`**: Active development branch. All internal and external changes land on `dev`.
- **Outside Contributors**: No outside contributors yet. When new contributors join, they may push/PR to `dev` only, not `main`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines, testing instructions, and pull request conventions.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

