#!/usr/bin/env bash
# waiter.sh — Watches the pinned Grok-delegations Antigravity conversation.
# Exits with 0 when a new bridge message arrives (wakes Antigravity).
set -euo pipefail

RESOLVE=$(python3 - <<'PY'
import sys, os
grok_side = os.path.expanduser("~/.config/bridge/grok_side")
if grok_side not in sys.path:
    sys.path.insert(0, grok_side)
from bridge_target import resolve_target
try:
    cid, brain = resolve_target()
    print(f"{cid}\t{brain}")
except Exception as e:
    print(f"\t", file=sys.stderr)
    print(f"resolve failed: {e}", file=sys.stderr)
    sys.exit(1)
PY
) || {
  echo "No pinned Grok delegations conversation. Waiting 5s..."
  sleep 5
  exit 1
}

CID=$(printf '%s' "$RESOLVE" | cut -f1)
ACTIVE_BRAIN=$(printf '%s' "$RESOLVE" | cut -f2)

if [ -z "$CID" ] || [ -z "$ACTIVE_BRAIN" ]; then
  echo "No pinned conversation found. Waiting 5s..."
  sleep 5
  exit 1
fi

MSG_DIR="$ACTIVE_BRAIN/$CID/.system_generated/messages"
mkdir -p "$MSG_DIR"

count_json() {
  find "$MSG_DIR" -maxdepth 1 -name "*.json" ! -name "cursor.json" ! -name "read.json" | wc -l
}

INITIAL_COUNT=$(count_json)
echo "Watching pinned Grok delegations conversation $CID @ $ACTIVE_BRAIN (initial JSON count: $INITIAL_COUNT)"

while true; do
  CURRENT_COUNT=$(count_json)
  if [ "$CURRENT_COUNT" -gt "$INITIAL_COUNT" ]; then
    echo "New message detected! Exiting 0."
    exit 0
  fi
  sleep 1
done
