#!/usr/bin/env python3
"""
send_to_antigravity.py — Grok → Antigravity task sender

Delivers into the pinned "Grok delegations" Antigravity conversation.
Independent of whichever Grok chat is active (MCP / CLI both use this target).

Usage:
    python3 send_to_antigravity.py [--wait] "Your task description"
"""

import datetime
import json
import os
import sys
import time
import uuid

# Allow importing sibling helper when run as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bridge_target import ensure_messages_dir, load_config, resolve_target  # noqa: E402


def main():
    wait_flag = False
    args = sys.argv[1:]
    if "--wait" in args:
        wait_flag = True
        args.remove("--wait")

    if not args:
        print("Usage: python3 send_to_antigravity.py [--wait] 'Task prompt'")
        sys.exit(1)

    prompt = " ".join(args)
    config = load_config()

    try:
        cid, brain_root = resolve_target()
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        print("   Open Antigravity, create/open the 'Grok delegations' chat with waiter running, then retry.")
        sys.exit(1)

    msg_id = str(uuid.uuid4())
    msg_dir = ensure_messages_dir(cid, brain_root)
    os.makedirs(config["grok_responses_dir"], exist_ok=True)

    reply_script = os.path.join(config["gemini_side_dir"], "reply_to_grok.py")
    resp_file = os.path.join(config["grok_responses_dir"], f"{msg_id}.txt")

    formatted_content = f"""**[AUTONOMOUS LOOP]** Grok has delegated a task via the bridge MCP/CLI.

**Context**: Delivered to the pinned Antigravity conversation "{config.get('pinned_conversation_title') or 'Grok delegations'}". Independent of any specific Grok chat session.

**Task**:
{prompt}

---
**[AUTONOMOUS LOOP — REPLY REQUIRED]**
When finished, reply by running:
python3 {reply_script} {msg_id} 'your response'
Or write directly to:
{resp_file}
Do NOT ask the user — execute and reply.
Then relaunch as a tracked background task:
bash ~/.config/bridge/gemini_side/waiter.sh
"""

    payload = {
        "id": msg_id,
        "recipient": cid,
        "sender": "grok",
        "priority": "MESSAGE_PRIORITY_HIGH",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "renderDetails": {"messageTitle": "🎯 Grok delegation"},
        "content": formatted_content,
    }

    msg_file = os.path.join(msg_dir, f"{msg_id}.json")
    with open(msg_file, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"✅ Task queued for Antigravity (Conversation: {cid})")
    print(f"   Title pin: {config.get('pinned_conversation_title') or 'Grok delegations'}")
    print(f"   Brain: {brain_root}")
    print(f"   Message ID: {msg_id}")
    print(f"   Message file: {msg_file}")
    print(f"   Response file: {resp_file}")

    if wait_flag:
        print(f"⏳ Waiting for response in {resp_file}...")
        start_t = time.time()
        while time.time() - start_t < 300:
            if os.path.exists(resp_file):
                with open(resp_file, "r") as rf:
                    content = rf.read()
                print("\n=== RESPONSE FROM ANTIGRAVITY ===")
                print(content)
                return
            time.sleep(1)


if __name__ == "__main__":
    main()
