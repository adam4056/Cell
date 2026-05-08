import os
import threading
import time

import requests
import yaml

from core import core as core_module
from core import inbox

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.yaml")
API = "https://api.telegram.org"

_process_lock = threading.Lock()


def _load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _send(token: str, chat_id: int, text: str) -> None:
    try:
        requests.post(
            f"{API}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},
            timeout=10,
        )
    except Exception:
        pass


def _handle_message(token: str, message: dict) -> None:
    text = message.get("text") or ""
    chat_id = message.get("chat", {}).get("id")
    user_id = message.get("from", {}).get("id")
    if not text or chat_id is None or user_id is None:
        return

    cfg = _load_config()
    allowed = cfg.get("telegram_user_id")

    if not allowed:
        _send(
            token,
            chat_id,
            f"Your Telegram user_id is: {user_id}\n"
            f"Add it to config.yaml as `telegram_user_id: {user_id}` to start chatting with Cell.",
        )
        return

    if int(allowed) != int(user_id):
        return

    with _process_lock:
        response = core_module.process(text)
    _send(token, chat_id, response or "(empty response)")


def _poll_loop(token: str) -> None:
    offset = 0
    while True:
        try:
            r = requests.get(
                f"{API}/bot{token}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=40,
            )
            data = r.json()
            if not data.get("ok"):
                time.sleep(5)
                continue
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if msg:
                    threading.Thread(
                        target=_handle_message, args=(token, msg), daemon=True
                    ).start()
        except Exception:
            time.sleep(5)


def start() -> bool:
    cfg = _load_config()
    token = (cfg.get("telegram_bot_token") or "").strip()
    if not token:
        return False
    threading.Thread(target=_poll_loop, args=(token,), daemon=True).start()
    allowed = cfg.get("telegram_user_id")
    if allowed:
        inbox.post(f"Telegram bot started (locked to user_id {allowed}).")
    else:
        inbox.post("Telegram bot started (unlocked — will reply with user_id to anyone).")
    return True
