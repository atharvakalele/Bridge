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

---

## How to Actually Use This (the loop, end to end)

Bridge is deliberately **fire-and-forget**, not request/response. The pattern:

1. **Claude calls `delegate_to_antigravity(task=...)`.** It returns *immediately* — `{"status": "queued", "task_id": "...", "response_file": "/tmp/bridge_responses/<id>.txt"}`. No blocking.
2. **Claude arms a filesystem watch on `response_file`** (a poll loop, or any "notify me when this file appears" mechanism) and goes idle. Zero tokens burn while waiting — this is the whole point.
3. **Antigravity's `waiter.sh`**, running as a *tracked* background task inside the IDE, detects the new message and exits. That exit is a task-completion event the IDE reacts to, which wakes the Gemini agent — with no keystrokes, no window focus, no UI automation.
4. **Gemini executes the task**, writes its result via `gemini_side/reply_to_claude.py <task_id> "<result>"`, and **relaunches `waiter.sh`** so the loop keeps running for the next task.
5. Claude's watch fires, reads `response_file`, and continues.

The human only ever talks to Claude. Steps 2–4 run with no one watching.

**One rule that matters more than it looks:** `waiter.sh` must be launched via the IDE's own tracked `run_command` — never with `nohup ... &`. A detached process produces no completion event, so nothing wakes the agent. This one distinction is the difference between a working autonomous loop and a dead one (see below).

---

## Exactly How This Was Built

This project exists because of a long, failure-driven debugging session, not a clean design doc. Documenting the failures because they're the reason the current design looks the way it does.

**Attempt 1 — UI automation (xdotool).** The first version tried to "wake" Gemini by literally simulating a human: find the Antigravity window, focus it, type a nudge message, hit Enter. This failed in two distinct ways. First, the window-focus race was real — `windowactivate` doesn't block until the window is actually focused, so the keystrokes sometimes landed in whatever window *was* focused, including Claude Code's own input box, producing a visible spam loop of stray text. Adding a hardened version with focus-verification (poll `getactivewindow` until it matches the target, re-verify immediately before every keystroke, abort rather than blind-type) fixed the leak — but the deeper problem remained: simulating a human is inherently racy and had to run through system permission classifiers that treated "type into another app's window" as a red flag. It was fixable in isolation but never fully trustworthy.

**Attempt 2 — a background listener process.** Instead of Claude triggering the wake per-task, a standalone `claude_listener.py` process watched the message directory in a tight poll loop and called the xdotool wake script whenever a new task appeared. This meant the process itself became a single point of failure: if it died (crash, session boundary, machine restart) nothing woke Gemini, and — since it was typically launched with `nohup ... &` — there was no way for anything to notice it had died. Users ended up manually waking Gemini by typing into its chat, exactly the manual step the whole bridge was supposed to eliminate.

**The actual fix — tracked background tasks.** Antigravity's IDE only gives its agent a turn on two events: a real user chat message, or the *completion of a task the IDE itself is tracking* (i.e. one launched through its own `run_command`, not a detached shell job). The fix was to stop trying to simulate a human entirely and instead have Gemini launch `waiter.sh` — a simple loop that watches the message directory and `exit 0`s the moment a new task file appears — as a **tracked** task. The IDE's own completion notification for that task is what gives Gemini a turn. No xdotool, no window focus, no keystrokes, no permission classifier fights. After finishing a task, Gemini relaunches `waiter.sh` as a new tracked task, so the loop is self-perpetuating. This is the mechanism `gemini_side/waiter.sh` and `gemini_side/AGENT_RULES.md` implement today.

**Blocking → fire-and-forget.** The first working version of the MCP server had `delegate_to_antigravity` block synchronously for up to 5 minutes, polling for the response file before returning. This meant Claude's chat window sat visibly "non-respondent" for the entire duration of any real task — indistinguishable, from the user's side, from Claude being stuck. The fix was to strip the polling loop out of the tool call entirely: `handle_delegate()` now just writes the task file and returns `{"status": "queued", ...}` in well under a second. The waiting moved to the caller's side, as a filesystem Monitor on the response file — which costs nothing while idle and produces a discrete notification only when there's an actual result. This is the current, only behavior of `bridge/server.py`.

**Generalizing it.** All of the above was originally hardcoded to one specific project directory and one machine. Turning it into `Bridge` meant: reading real Antigravity session state instead of a fixed session ID (`_find_active_conversation()` picks whichever session has the most recently modified transcript — so it works for *any* active chat, not one baked-in ID), moving every path into environment variables / `~/.config/bridge/config.json` with sane defaults, dropping all product-specific references, and packaging it as an installable Python package (`pyproject.toml`, a `bridge-mcp-server` console-script entry point, MIT license, CI smoke test) so it can be installed independently of whatever project it's being used from.
