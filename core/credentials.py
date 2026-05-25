"""Credentials store — secrets and config the LLM should never see.

All values are stored in project-root `credentials.json`.
LLM only references them by key name (e.g. ``OPEN_METEO_API_KEY``).

Usage from generated functions:
    from core.credentials import get_credential
    api_key = get_credential("OPEN_METEO_API_KEY")
"""
import json
import os
import threading

_CREDENTIALS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "credentials.json"
)
_lock = threading.Lock()


def _load() -> dict:
    if not os.path.exists(_CREDENTIALS_FILE):
        return {}
    try:
        with open(_CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(_CREDENTIALS_FILE), exist_ok=True)
    with open(_CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get(key: str) -> str | None:
    with _lock:
        return _load().get(key)


def set(key: str, value: str) -> None:
    with _lock:
        data = _load()
        data[key] = value
        _save(data)


def delete(key: str) -> bool:
    with _lock:
        data = _load()
        if key in data:
            del data[key]
            _save(data)
            return True
        return False


def list_keys() -> list[str]:
    with _lock:
        return sorted(_load().keys())


def get_credential(key: str) -> str:
    """Public API for generated functions. Raises KeyError if not found."""
    val = get(key)
    if val is None:
        raise KeyError(f"credential not found: {key}")
    return val
