# Grok ↔ Antigravity (always on)

This machine’s worker is MCP **agy-cli** only (`agy_run`, `agy_status`, `agy_models`, `agy_preview`, `agy_kill`). Grok-AG only. Do not add this server to Cline or Claude.

AG does **not** message Grok chats. Closing a Grok chat does not kill AG and does not destroy jobs. Results are files: `~/.config/bridge/agy_cli/jobs/<job_id>/` (`notify`, `result.json`, `job.log`). Another chat uses `agy_status` (no id = live job) or `watch_job.py`.

## Do

1. `agy_run` with full `task` and absolute `cwd`. Default model `gemini-3.7-flash-medium`. Never Opus.
2. It returns now: `STARTED` or `QUEUED` + `job_id`.
3. Background monitor, do not block: `python3 ~/.config/bridge/agy_cli/watch_job.py <job_id>`
4. Keep talking. On SUCCESS/ERROR/CRASH/TIMEOUT/NETWORK/CANCELED, `agy_status` and continue.
5. Same `cwd` continues AG history unless `new_session=true`.
6. `QUEUED` means wait; the supervisor starts it next. Do not start a second AG.
7. The `AG-job` pane is logs only. Closing it does not kill AG. If `preview_open` is false while running, ask before `agy_preview` reopen.
8. User says stop/kill/cancel AG → `agy_kill`. Do not pkill Grok.

## Do not

- Run `agy` or `agy-job` inside this chat
- Start `waiter.sh` or use `bridge-mcp-server` / GUI inbox
- Expect AG to ping the chat that launched it
