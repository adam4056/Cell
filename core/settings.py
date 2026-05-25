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


def web_auth_token() -> str:
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    try:
        import yaml

        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            return str(cfg.get("web_auth_token", "") or "").strip()
    except Exception:
        pass
    stored = _load().get("web_auth_token", "")
    return str(stored).strip() if stored else ""


AMBIENT_DEFAULTS = {
    "enabled": False,
    "interval_minutes": 30,
    "quiet_hours": [22, 8],  # [start_hour, end_hour); wraps midnight if start > end
    "max_per_day": 6,
    "cooldown_after_user_min": 5,
}


def ambient_config() -> dict:
    cfg = dict(AMBIENT_DEFAULTS)
    stored = _load().get("ambient", {})
    if isinstance(stored, dict):
        cfg.update({k: v for k, v in stored.items() if k in AMBIENT_DEFAULTS})
    return cfg


def set_ambient(key: str, value) -> None:
    if key not in AMBIANT_DEFAULTS:
        raise ValueError(f"unknown ambient key: {key}")
    data = _load()
    amb = data.get("ambient", {})
    if not isinstance(amb, dict):
        amb = {}
    amb[key] = value
    data["ambient"] = amb
    _save(data)


def is_auto_route() -> bool:
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    try:
        import yaml

        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            return bool(cfg.get("auto_route", False))
    except Exception:
        pass
    return False
