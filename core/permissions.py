"""
Permission gate v2 — granular access control for agent actions.

Types:
  file_read      — read user files
  file_write     — write/modify user files
  shell_exec     — execute shell commands
  browser_access — fetch web pages
  code_execution — run code in sandbox
  network_access — general network calls (non-browser)

Each type can be: always_allow, ask, always_deny
"""

import hashlib
import json
import os
import threading
from typing import Any

PERMISSIONS_FILE = os.path.join(os.path.expanduser("~"), ".cell-2", "permissions.json")
DIALOG_TIMEOUT = 15 * 60  # 15 minutes

_lock = threading.Lock()
_dialog_fn = None

# Permission categories
PERM_CATEGORIES = {
    "file_read": "Read files",
    "file_write": "Write/modify files",
    "shell_exec": "Execute shell commands",
    "browser_access": "Access websites",
    "code_execution": "Execute code in sandbox",
    "network_access": "Network access (non-browser)",
}


def set_dialog(fn) -> None:
    """UI registers dialog callback."""
    global _dialog_fn
    _dialog_fn = fn


def _load() -> dict:
    if not os.path.exists(PERMISSIONS_FILE):
        return {}
    try:
        with open(PERMISSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(PERMISSIONS_FILE), exist_ok=True)
    tmp = PERMISSIONS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PERMISSIONS_FILE)


def _key(perm_type: str, detail: str) -> str:
    h = hashlib.sha256(f"{perm_type}\0{detail}".encode("utf-8")).hexdigest()[:16]
    return f"{perm_type}:{h}"


def _saved_decision(perm_type: str, detail: str) -> str | None:
    data = _load()
    return data.get(_key(perm_type, detail))


def _save_decision(perm_type: str, detail: str, decision: str) -> None:
    with _lock:
        data = _load()
        data[_key(perm_type, detail)] = decision
        _save(data)


def _prompt_with_timeout(perm_type: str, detail: str) -> str:
    if _dialog_fn is None:
        return "skip"
    result_box: list = []
    done = threading.Event()

    def runner():
        try:
            label = PERM_CATEGORIES.get(perm_type, perm_type)
            result_box.append(_dialog_fn(label, detail))
        except Exception:
            result_box.append("skip")
        finally:
            done.set()

    threading.Thread(target=runner, daemon=True).start()
    if not done.wait(DIALOG_TIMEOUT):
        return "skip"
    return result_box[0] if result_box else "skip"


def request(perm_type: str, detail: str) -> str:
    """Returns 'allow', 'deny', or 'skip'. Persists 'always_*' decisions."""
    saved = _saved_decision(perm_type, detail)
    if saved == "always_allow":
        return "allow"
    if saved == "always_deny":
        return "deny"

    decision = _prompt_with_timeout(perm_type, detail)

    if decision == "always_allow":
        _save_decision(perm_type, detail, "always_allow")
        return "allow"
    if decision == "always_deny":
        _save_decision(perm_type, detail, "always_deny")
        return "deny"
    if decision in ("allow", "deny", "skip"):
        return decision
    return "skip"


def set_policy(perm_type: str, policy: str) -> None:
    """Set global policy for a permission type."""
    with _lock:
        data = _load()
        data[f"_policy:{perm_type}"] = policy
        _save(data)


def get_policy(perm_type: str) -> str:
    """Get global policy. Returns 'ask' by default."""
    data = _load()
    return data.get(f"_policy:{perm_type}", "ask")


def list_policies() -> dict[str, str]:
    """List all permission policies."""
    data = _load()
    policies = {}
    for perm_type in PERM_CATEGORIES:
        policies[perm_type] = data.get(f"_policy:{perm_type}", "ask")
    return policies


def reset_all() -> None:
    """Clear all permission decisions."""
    with _lock:
        _save({})
