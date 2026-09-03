---
name: agy-cli
description: Delegate coding work to Antigravity CLI via MCP agy_run. Use whenever the user wants AG, Antigravity, agy, or a detached worker to implement, refactor, test, or push — not Grok writing the files.
---

# Delegate to Antigravity CLI

MCP server `agy-cli` is user-scoped. Tools: `agy_run`, `agy_status`, `agy_models`, `agy_preview`.

AG is a **detached worker**. Do not run `agy` or `agy-job` inside this chat (that dies when the user types). Do not start `waiter.sh`.

## Every job

1. `search_tool` then `agy_run` with a full `task` and absolute `cwd`.
2. Default model: `gemini-3.7-flash-medium`. Never Opus. Never Gemini Pro unless the user writes it.
3. `agy_run` returns immediately (`STARTED` or `QUEUED`) with `job_id`.
4. Start a background monitor; do not block the turn:
   `python3 ~/.config/bridge/agy_cli/watch_job.py <job_id>`
   One line: `SUCCESS|ERROR|CRASH|TIMEOUT|NETWORK|CANCELED <id>`
5. Keep talking. When the monitor fires, `agy_status` and continue.

Same `cwd` continues the last AG conversation. Pass `new_session=true` only for a fresh AG chat.

## Queue

If status is `QUEUED`, a job is already running. The new job starts when that one finishes. Do not spawn a second AG yourself.

## Log pane

The `AG-job` window is **logs only**. Typing there does not talk to AG.

- Closing it does **not** kill the job.
- Logs stay until the user closes them. Do not close Grok's terminal (title is not `AG-job`).
- If `agy_status` shows `preview_open: false` while the job is still running, ask: "You closed the AG log pane. Want it back?" Reopen only with `agy_preview` `action=reopen` after they say yes.

## Finish kinds

- `SUCCESS` — AG finished the task
- `ERROR` — AG reported failure
- `CRASH` — process died with no result
- `TIMEOUT` — we cut it off at the time limit
- `NETWORK` — connection / auth / 429 / 5xx
- `CANCELED` — stopped before completion
