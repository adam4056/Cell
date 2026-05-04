"""Session boundary tracker — PersonaVLM-style.

The Space is one infinite chat, but memory updates batch on session boundaries:
a session ends after `IDLE_TIMEOUT_SEC` of silence (default 60 min) or on explicit
`finalize()`. The next user turn after an end starts a fresh session.

State persisted to memory/session.json:
  current   = active session dict or null
  closed    = list of recently closed session metadata (capped, for debugging)

Each session dict:
  id              : monotonic int
  started_at      : ISO timestamp of first turn
  last_turn_at    : ISO timestamp of most recent user turn
  message_offset  : index into context_store at session start
  turn_count      : # of user turns in this session
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "memory")
SESSION_FILE = os.path.join(MEMORY_DIR, "session.json")

IDLE_TIMEOUT_SEC = 60 * 60  # 60 minutes
_CLOSED_KEEP = 50

_LOCK = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _parse(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _empty_state() -> dict[str, Any]:
    return {"current": None, "closed": [], "next_id": 1}


def _load() -> dict[str, Any]:
    if not os.path.exists(SESSION_FILE):
        return _empty_state()
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("current", None)
        data.setdefault("closed", [])
        data.setdefault("next_id", 1)
        return data
    except Exception:
        return _empty_state()


def _save(state: dict[str, Any]) -> None:
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with _LOCK:
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)


def current() -> dict[str, Any] | None:
    return _load().get("current")


def is_idle_expired(state: dict[str, Any] | None = None) -> bool:
    state = state if state is not None else _load()
    cur = state.get("current")
    if not cur:
        return False
    last = _parse(cur.get("last_turn_at", ""))
    if last is None:
        return False
    return (_now() - last).total_seconds() > IDLE_TIMEOUT_SEC


def touch(message_offset: int) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Record a user turn. Returns (current_session, just_closed_session_or_none).

    If the previous session was idle-expired, it is closed first; the caller
    should run per-session curation on `just_closed_session`. A new session is
    then started. Otherwise the existing session's counters tick forward.
    """
    state = _load()
    closed: dict[str, Any] | None = None

    cur = state.get("current")
    if cur and is_idle_expired(state):
        cur["closed_at"] = _now_iso()
        cur["closed_reason"] = "idle_timeout"
        state["closed"] = (state.get("closed", []) + [cur])[-_CLOSED_KEEP:]
        closed = cur
        cur = None

    if cur is None:
        sid = int(state.get("next_id", 1))
        cur = {
            "id": sid,
            "started_at": _now_iso(),
            "last_turn_at": _now_iso(),
            "message_offset": int(message_offset),
            "turn_count": 1,
        }
        state["next_id"] = sid + 1
    else:
        cur["last_turn_at"] = _now_iso()
        cur["turn_count"] = int(cur.get("turn_count", 0)) + 1

    state["current"] = cur
    _save(state)
    return cur, closed


def finalize(reason: str = "explicit") -> dict[str, Any] | None:
    """Close the active session immediately. Returns the closed session, or None."""
    state = _load()
    cur = state.get("current")
    if not cur:
        return None
    cur["closed_at"] = _now_iso()
    cur["closed_reason"] = reason
    state["closed"] = (state.get("closed", []) + [cur])[-_CLOSED_KEEP:]
    state["current"] = None
    _save(state)
    return cur


def reset() -> None:
    _save(_empty_state())
