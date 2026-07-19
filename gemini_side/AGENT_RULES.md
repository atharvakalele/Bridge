# CRITICAL: Auto-Wake Loop Startup — Launch waiter.sh on EVERY session start

On EVERY new conversation or session start, you MUST immediately launch `waiter.sh` as a TRACKED background task so Claude Code delegations auto-wake you.

Run:
```python
run_command(CommandLine="bash ~/.config/bridge/gemini_side/waiter.sh", WaitMsBeforeAsync=500)
```

After completing ANY delegated task from Claude, you MUST relaunch `waiter.sh` the same way. Never use `nohup` or `&` — the task must be IDE-tracked.
