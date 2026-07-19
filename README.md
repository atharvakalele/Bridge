# Claude Code ↔ Antigravity IDE Bridge

An installable, general-purpose bidirectional bridge that establishes an autonomous loop between **Claude Code** (running on your command line) and **Antigravity IDE** (the Gemini-powered developer environment).

## Why This Exists

Typical agentic setups require constant human intervention to copy-paste tasks between different environments. The Bridge automates this loop, allowing Claude Code to programmatically delegate heavy lifting (like long builds, code modifications, or multi-step execution tasks) directly to the Antigravity IDE.

### Replaces Flaky UI-Automation
Earlier versions of this bridge attempted to use window-targeting tools like `xdotool` and `wmctrl` to inject keypresses into the IDE interface to wake up the agent. Those methods were unreliable, prone to typing in the wrong window, and easily blocked. 

The new Bridge relies on a robust **Tracked Waiter Loop** and file-system monitors, allowing direct, reliable API-free integration that works seamlessly in the background.

---

## Architecture

```
                                  +-----------------------+
                                  |      Claude Code      |
                                  |  (User Command Line)  |
                                  +-----------+-----------+
                                              |
                                     (MCP Tool Calls)
                                              |
                                              v
+-------------------------+       +-----------+-----------+
|    Antigravity IDE      |       |      Bridge MCP       |
|    (Gemini Agent)       |       |        Server         |
+------------+------------+       +-----------+-----------+
             |                                |
   (Tracked Waiter Loop)               (JSON Messages)
             |                                |
             v                                v
+------------+--------------------------------+-----------+
|                   Shared Communication Paths            |
|                   (e.g., /tmp/bridge_responses/)        |
+---------------------------------------------------------+
```

---

## Quickstart

### 1. Installation
Run the installer script:
```bash
bash scripts/install.sh
```

### 2. Register MCP Server
Add the server to Claude Code:
```bash
claude mcp add bridge-mcp-server -- bridge-mcp-server
```

### 3. Verify Setup
Check if all directories and commands are registered:
```bash
bash scripts/start_bridge.sh
```

### 4. Running the Loop
Since delegations are fire-and-forget, they return immediately. You must run a Monitor on the Claude Code side to watch for task responses:
```bash
tail -f /tmp/bridge_responses/*.txt
```

---

## Configurable Options
Configuration is loaded from `~/.config/bridge/config.json`. The following settings can also be overridden using environment variables:

| Env Var | Default | Description |
|---|---|---|
| `BRIDGE_IDE_BRAIN_ROOT` | `~/.gemini/antigravity-ide/brain` | Location of Antigravity IDE log directories |
| `BRIDGE_RESPONSES_DIR` | `/tmp/bridge_responses` | Target folder for task responses |
| `BRIDGE_INBOX_DIR` | `/tmp/bridge_to_claude` | Target folder for proactive inbox notifications |
| `BRIDGE_TMP_DIR` | `/tmp/bridge` | Base directory for responses and inbox (alternative to separate vars) |

---

## Tools Exposed
The Bridge MCP server exposes the following tools to Claude Code:
1. **`delegate_to_antigravity`**: Sends a task description to Antigravity and returns immediately with a task_id and response_file path. The caller must watch this response_file (e.g. via a filesystem Monitor) for the actual result.
2. **`check_antigravity_inbox`**: Checks for proactive messages sent by the Antigravity agent.
3. **`list_antigravity_models`**: Lists available model tiers that can be requested (e.g. Flash vs Pro).
4. **`read_workspace_file`**: Reads a file directly from the shared workspace path.

---

## Concurrency & Multi-Instance Usage
Since the Antigravity IDE configuration is global for the user (at `~/.config/bridge/config.json`), concurrent Claude Code instances running on the same machine will share the same communication directories by default. 

- **Task Delegations**: Safe. Because tasks use unique UUIDs, delegation files will not overwrite or collide.
- **Proactive Inbox**: Collapsible. Proactive inbox notifications are read globally, meaning a message meant for one Claude session could be retrieved by another concurrent session.
- **Isolation**: To isolate concurrent sessions, configure separate `BRIDGE_TMP_DIR` (or `BRIDGE_RESPONSES_DIR` / `BRIDGE_INBOX_DIR`) environment variables on both the Claude Code and Antigravity IDE sides.
