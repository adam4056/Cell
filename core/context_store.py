import json
import os
import tempfile
import threading

CONTEXT_FILE = os.path.join(os.path.dirname(__file__), "..", "context.json")
_lock = threading.Lock()


def _load() -> list:
    if not os.path.exists(CONTEXT_FILE):
        return []
    with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(history: list) -> None:
    d = os.path.dirname(CONTEXT_FILE)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".context-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONTEXT_FILE)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def append(role: str, content: str) -> None:
    with _lock:
        history = _load()
        history.append({"role": role, "content": content})
        _save(history)


def get_all() -> list:
    with _lock:
        return _load()


def replace_all(history: list) -> None:
    with _lock:
        _save(history)
