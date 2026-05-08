"""Isolated chat contexts (threads).

Space (the infinite context) lives in context.json and feeds memory curation.
Chats live here — separate JSON per chat, read-only access to memory, no
curation. They exist to keep one-off questions from polluting Space.
"""

import json
import os
import tempfile
import threading
import time
import uuid

CHATS_DIR = os.path.join(os.path.dirname(__file__), "..", "chats")
_lock = threading.Lock()


def _ensure_dir() -> None:
    os.makedirs(CHATS_DIR, exist_ok=True)


def _path(chat_id: str) -> str:
    safe = "".join(c for c in chat_id if c.isalnum() or c in "-_")
    if not safe:
        raise ValueError(f"invalid chat_id: {chat_id}")
    return os.path.join(CHATS_DIR, f"{safe}.json")


def _read(chat_id: str) -> dict | None:
    p = _path(chat_id)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(chat: dict) -> None:
    _ensure_dir()
    p = _path(chat["id"])
    fd, tmp = tempfile.mkstemp(dir=CHATS_DIR, prefix=".chat-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(chat, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def create(title: str = "") -> dict:
    chat = {
        "id": uuid.uuid4().hex[:8],
        "title": title or "New chat",
        "created": time.time(),
        "history": [],
    }
    with _lock:
        _write(chat)
    return chat


def get(chat_id: str) -> dict | None:
    with _lock:
        return _read(chat_id)


def list_all() -> list[dict]:
    _ensure_dir()
    with _lock:
        out = []
        for fname in os.listdir(CHATS_DIR):
            if not fname.endswith(".json") or fname.startswith("."):
                continue
            try:
                with open(os.path.join(CHATS_DIR, fname), "r", encoding="utf-8") as f:
                    chat = json.load(f)
                out.append({
                    "id": chat["id"],
                    "title": chat.get("title", "Untitled"),
                    "created": chat.get("created", 0),
                    "messages": len(chat.get("history", [])),
                })
            except Exception:
                continue
    out.sort(key=lambda c: -c.get("created", 0))
    return out


def append(chat_id: str, role: str, content: str) -> None:
    with _lock:
        chat = _read(chat_id)
        if chat is None:
            raise KeyError(f"chat not found: {chat_id}")
        chat.setdefault("history", []).append({"role": role, "content": content})
        _write(chat)


def set_title(chat_id: str, title: str) -> None:
    with _lock:
        chat = _read(chat_id)
        if chat is None:
            return
        chat["title"] = title[:80]
        _write(chat)


def delete(chat_id: str) -> bool:
    with _lock:
        p = _path(chat_id)
        if os.path.exists(p):
            os.remove(p)
            return True
    return False
