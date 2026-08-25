#!/usr/bin/env python3
"""Resolve the pinned Antigravity conversation for Grok↔AG bridge.

The bridge must NOT follow whichever conversation is newest, and must NOT be
tied to a Grok chat session. It always targets the dedicated Antigravity
conversation configured as the Grok delegations inbox.
"""

from __future__ import annotations

import json
import os
import sqlite3
import glob
from typing import Optional, Tuple, List

CONFIG_PATH = os.path.expanduser("~/.config/bridge/config.json")
TARGET_PATH = os.path.expanduser("~/.config/bridge/antigravity_target.json")

DEFAULT_BRAIN_ROOTS = [
    "~/.gemini/antigravity/brain",
    "~/.gemini/antigravity-ide/brain",
    "~/.gemini/antigravity-cli/brain",
]


def _expand(path: str) -> str:
    return os.path.expanduser(path)


def load_config() -> dict:
    cfg = {
        "brain_root": _expand("~/.gemini/antigravity/brain"),
        "brain_roots": [_expand(p) for p in DEFAULT_BRAIN_ROOTS],
        "pinned_conversation_id": None,
        "pinned_conversation_title": "Grok delegations",
        "responses_dir": _expand("~/coding-agent/bridge_responses"),
        "grok_responses_dir": _expand("~/coding-agent/grok_responses"),
        "inbox_dir": "/tmp/bridge_to_claude",
        "gemini_side_dir": _expand("~/.config/bridge/gemini_side"),
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                user = json.load(f)
            for k, v in user.items():
                if k == "brain_roots" and isinstance(v, list):
                    cfg["brain_roots"] = [_expand(p) for p in v]
                elif isinstance(v, str):
                    cfg[k] = _expand(v) if ("/" in v or v.startswith("~")) else v
                elif v is not None:
                    cfg[k] = v
        except Exception:
            pass

    # Overlay dedicated target file (authoritative pin)
    if os.path.exists(TARGET_PATH):
        try:
            with open(TARGET_PATH) as f:
                target = json.load(f)
            if target.get("conversation_id"):
                cfg["pinned_conversation_id"] = target["conversation_id"]
            if target.get("title"):
                cfg["pinned_conversation_title"] = target["title"]
            if target.get("brain_root"):
                cfg["brain_root"] = _expand(target["brain_root"])
        except Exception:
            pass

    roots: List[str] = []
    for r in [cfg["brain_root"], *cfg.get("brain_roots", [])]:
        r = _expand(r)
        if r not in roots:
            roots.append(r)
    cfg["brain_roots"] = roots
    cfg["brain_root"] = roots[0]
    return cfg


def save_target(conversation_id: str, title: str = "Grok delegations", brain_root: Optional[str] = None) -> None:
    cfg = load_config()
    brain_root = _expand(brain_root or cfg["brain_root"])
    payload = {
        "conversation_id": conversation_id,
        "title": title,
        "brain_root": brain_root,
    }
    os.makedirs(os.path.dirname(TARGET_PATH), exist_ok=True)
    with open(TARGET_PATH, "w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    # Keep config.json in sync too
    try:
        user = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                user = json.load(f)
        user["pinned_conversation_id"] = conversation_id
        user["pinned_conversation_title"] = title
        user["brain_root"] = brain_root
        with open(CONFIG_PATH, "w") as f:
            json.dump(user, f, indent=2)
            f.write("\n")
    except Exception:
        pass


def _conversation_exists(brain_root: str, cid: str) -> bool:
    return os.path.isdir(os.path.join(brain_root, cid, ".system_generated", "messages")) or os.path.isdir(
        os.path.join(brain_root, cid)
    )


def _find_by_title(title: str, brain_roots: List[str]) -> Optional[Tuple[str, str]]:
    """Best-effort title match via sqlite conversation DBs / summaries strings."""
    title_l = title.lower()
    conv_dirs = [
        _expand("~/.gemini/antigravity/conversations"),
        _expand("~/.gemini/antigravity-ide/conversations"),
        _expand("~/.gemini/antigravity-cli/conversations"),
    ]
    candidates = []
    for d in conv_dirs:
        for db in glob.glob(os.path.join(d, "*.db")):
            try:
                con = sqlite3.connect(db)
                cur = con.cursor()
                blob = b""
                for table in ("trajectory_metadata_blob", "steps", "gen_metadata"):
                    try:
                        for row in cur.execute(f"SELECT * FROM {table}"):
                            for v in row:
                                if isinstance(v, (bytes, bytearray)):
                                    blob += bytes(v)
                    except Exception:
                        pass
                con.close()
                text = blob.decode("utf-8", "ignore")
                if title_l in text.lower():
                    cid = os.path.basename(db)[:-3]
                    mtime = os.path.getmtime(db)
                    candidates.append((mtime, cid, db))
            except Exception:
                continue
    if not candidates:
        return None
    candidates.sort(reverse=True)
    _, cid, _ = candidates[0]
    for brain in brain_roots:
        if _conversation_exists(brain, cid):
            return cid, brain
    return cid, brain_roots[0]


def resolve_target() -> Tuple[str, str]:
    """Return (conversation_id, brain_root) for bridge deliveries.

    Raises RuntimeError if no pinned/dedicated conversation is available.
    """
    cfg = load_config()
    roots = cfg["brain_roots"]
    pinned = cfg.get("pinned_conversation_id")
    title = cfg.get("pinned_conversation_title") or "Grok delegations"

    if pinned:
        for brain in roots:
            if _conversation_exists(brain, pinned):
                return pinned, brain
        return pinned, roots[0]

    found = _find_by_title(title, roots)
    if found:
        cid, brain = found
        save_target(cid, title=title, brain_root=brain)
        return cid, brain

    raise RuntimeError(
        f"No pinned Antigravity conversation for Grok delegations. "
        f"Expected title '{title}' or pinned_conversation_id in {TARGET_PATH}."
    )


def ensure_messages_dir(cid: str, brain_root: str) -> str:
    msg_dir = os.path.join(brain_root, cid, ".system_generated", "messages")
    os.makedirs(msg_dir, exist_ok=True)
    return msg_dir
