#!/usr/bin/env bash
# grok_waiter.sh — Watches /tmp/bridge_to_grok for incoming messages for Grok CLI.
set -euo pipefail

INBOX_DIR="/tmp/bridge_to_grok"
mkdir -p "$INBOX_DIR"

count_json() {
  find "$INBOX_DIR" -maxdepth 1 -name "*.json" | wc -l
}

INITIAL_COUNT=$(count_json)
echo "Watching Grok inbox: $INBOX_DIR (initial count: $INITIAL_COUNT)"

while true; do
  CURRENT_COUNT=$(count_json)
  if [ "$CURRENT_COUNT" -gt "$INITIAL_COUNT" ]; then
    echo "New task for Grok detected! Exiting 0."
    exit 0
  fi
  sleep 1
done
