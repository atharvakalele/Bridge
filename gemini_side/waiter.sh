#!/usr/bin/env bash
# waiter.sh — Watches the active conversation message directory.
# Exits with 0 when a new message from Claude Code arrives,
# which triggers the reactive system wakeup for Antigravity.
set -euo pipefail

# 1. Detect active session using brain root configuration
BRAIN_ROOT=$(python3 -c "
import os, json
config_path = os.path.expanduser('~/.config/bridge/config.json')
brain_root = os.path.expanduser('~/.gemini/antigravity-ide/brain')
if os.path.exists(config_path):
    try:
        with open(config_path, 'r') as f:
            brain_root = os.path.expanduser(json.load(f).get('brain_root', brain_root))
    except: pass
print(os.environ.get('BRIDGE_IDE_BRAIN_ROOT', brain_root))
")

CID=$(python3 -c "
import os
brain = '$BRAIN_ROOT'
best_id, best_mt = None, 0
if os.path.exists(brain):
    for e in os.listdir(brain):
        f = os.path.join(brain, e)
        if not os.path.isdir(f) or e == 'tempmediaStorage': continue
        t = os.path.join(f, '.system_generated', 'logs', 'transcript.jsonl')
        if os.path.exists(t):
            mt = os.path.getmtime(t)
            if mt > best_mt: best_mt, best_id = mt, e
print(best_id or '')
")

if [ -z "$CID" ]; then
  echo "No active conversation found. Waiting 5s before check..."
  sleep 5
  exit 1
fi

MSG_DIR="$BRAIN_ROOT/$CID/.system_generated/messages"
mkdir -p "$MSG_DIR"

# Count current json files (excluding cursor.json, read.json)
count_json() {
  find "$MSG_DIR" -maxdepth 1 -name "*.json" ! -name "cursor.json" ! -name "read.json" | wc -l
}

INITIAL_COUNT=$(count_json)
echo "Watching messages in $CID (initial JSON count: $INITIAL_COUNT)"

while true; do
  CURRENT_COUNT=$(count_json)
  if [ "$CURRENT_COUNT" -gt "$INITIAL_COUNT" ]; then
    echo "New message detected! Exiting to wake up Antigravity."
    exit 0
  fi
  sleep 1
done
