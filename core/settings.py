import json
import os
import threading

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "settings.json")
_lock = threading.Lock()


def _load() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    with _lock:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def get(key: str, default=None):
    return _load().get(key, default)


def set(key: str, value) -> None:
    data = _load()
    data[key] = value
    _save(data)


def is_first_run() -> bool:
    return not _load().get("onboarding_completed", False)


def complete_onboarding() -> None:
    set("onboarding_completed", True)
