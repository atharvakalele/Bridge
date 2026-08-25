# Agent rules

## CLI / headless (`agy -p`)

Never launch `waiter.sh`. Never start a tracked daemon. Complete the task and exit.

## GUI only

On a new **IDE GUI** conversation, you MAY launch a tracked waiter:

```
run_command(CommandLine="bash ~/.config/bridge/gemini_side/waiter.sh", WaitMsBeforeAsync=500)
```

Do not use `nohup` or `&`.

- Claude: `python3 ~/.config/bridge/gemini_side/reply_to_claude.py <message_id> 'response'`
- Grok: `python3 ~/.config/bridge/gemini_side/reply_to_grok.py <message_id> 'response'`
