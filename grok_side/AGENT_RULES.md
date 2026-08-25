# Grok Autonomous Bridge Rules

1. Always use `agy_run` or `send_to_antigravity.py` to send tasks.
2. Default model is `gemini-3.7-flash-medium`. Never invoke Opus.
3. For CLI print mode (`agy -p`): never launch waiter.sh or infinite loops.
4. For GUI mode: ensure Antigravity runs `bash ~/.config/bridge/gemini_side/waiter.sh`.
