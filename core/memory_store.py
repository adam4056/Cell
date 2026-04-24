import json
import os
import tempfile
import threading

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "memory.json")
_lock = threading.Lock()


def _load() -> dict:
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    d = os.path.dirname(MEMORY_FILE)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".memory-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, MEMORY_FILE)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def set(key: str, value: str) -> None:
    with _lock:
        data = _load()
        data[key] = value
        _save(data)


def get(key: str) -> str | None:
    with _lock:
        return _load().get(key)


def delete(key: str) -> bool:
    with _lock:
        data = _load()
        if key not in data:
            return False
        del data[key]
        _save(data)
        return True


def get_all() -> dict:
    with _lock:
        return _load()
