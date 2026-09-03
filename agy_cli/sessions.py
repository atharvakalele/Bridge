#!/usr/bin/env python3
"""Per-cwd AG CLI conversation map.

agy --continue is global last-chat, not per project. We store conversation_id
keyed by realpath(cwd) so follow-up tasks in the same repo keep history.
"""
from __future__ import annotations

import json
import os

SESSIONS_PATH = os.path.expanduser("~/.config/bridge/agy_cli/sessions.json")


def _key(cwd: str) -> str:
    try:
        return os.path.realpath(os.path.expanduser(cwd))
    except Exception:
        return os.path.expanduser(cwd)


def load_sessions() -> dict:
    try:
        with open(SESSIONS_PATH) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_sessions(data: dict) -> None:
    os.makedirs(os.path.dirname(SESSIONS_PATH), exist_ok=True)
    tmp = SESSIONS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, SESSIONS_PATH)


def get_conversation(cwd: str) -> str | None:
    rec = load_sessions().get(_key(cwd)) or {}
    cid = rec.get("conversation_id")
    return cid if cid else None


def remember(cwd: str, conversation_id: str | None, job_id: str | None = None, status: str | None = None) -> None:
    if not conversation_id:
        return
    data = load_sessions()
    data[_key(cwd)] = {
        "conversation_id": conversation_id,
        "job_id": job_id,
        "status": status,
        "cwd": _key(cwd),
    }
    save_sessions(data)


def forget(cwd: str) -> None:
    data = load_sessions()
    data.pop(_key(cwd), None)
    save_sessions(data)
