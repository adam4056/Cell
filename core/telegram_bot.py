"""Telegram bot — full conversation relay with /commands, inbox, typing.

All messages go through the same process() as TUI. The bot acts as a
mirror of the TUI session: same brain, same memory, same context.
"""
import os
import threading
import time

import requests
import yaml

from core import context_store, inbox, settings
from core.core import _run_ambient_tick, process
from core.memory_engine import engine as memory_engine
from core.runner import cancel_active

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.yaml")
API = "https://api.telegram.org"

_lock = threading.Lock()
_active_chat_id: int | None = None


def _cfg():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _token() -> str:
    return (_cfg().get("telegram_bot_token") or "").strip()


def _allowed_user_id() -> int | None:
    v = _cfg().get("telegram_user_id")
    if v is None or v == "" or v == "null":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _send(chat_id: int, text: str, reply_to: int | None = None) -> int | None:
    """Send a message. Splits >4000 chars into chunks. Returns last msg id."""
    chunks = _split_text(text)
    last_msg_id = None
    for chunk in chunks:
        payload = {"chat_id": chat_id, "text": chunk}
        if reply_to is not None and last_msg_id is None:
            payload["reply_to_message_id"] = reply_to
        try:
            r = requests.post(
                f"{API}/bot{_token()}/sendMessage",
                json=payload,
                timeout=10,
            )
            data = r.json()
            if data.get("ok"):
                last_msg_id = data["result"]["message_id"]
        except Exception:
            pass
    return last_msg_id


def _send_action(chat_id: int, action: str = "typing") -> bool:
    """Send chat action (typing indicator, etc.). Returns True on success."""
    try:
        r = requests.post(
            f"{API}/bot{_token()}/sendChatAction",
            json={"chat_id": chat_id, "action": action},
            timeout=5,
        )
        return r.json().get("ok", False)
    except Exception:
        return False


def _split_text(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1 or split_at < limit // 2:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


def _download_file(file_id: str) -> str | None:
    """Download a Telegram file to a temp path. Returns path or None."""
    try:
        r = requests.get(
            f"{API}/bot{_token()}/getFile",
            params={"file_id": file_id},
            timeout=10,
        )
        data = r.json()
        if not data.get("ok"):
            return None
        file_path = data["result"]["file_path"]
        url = f"https://api.telegram.org/file/bot{_token()}/{file_path}"
        import tempfile

        ext = os.path.splitext(file_path)[1] or ".bin"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        r2 = requests.get(url, timeout=60)
        tmp.write(r2.content)
        tmp.close()
        return tmp.name
    except Exception:
        return None


def _extract_text(message: dict) -> str:
    text = message.get("text") or message.get("caption") or ""
    return text.strip()


def _handle_command(chat_id: int, text: str) -> bool:
    """Handle /commands. Returns True if handled."""
    parts = text.split(maxsplit=2)
    cmd = parts[0].lower().split("@")[0]

    if cmd == "/help":
        _send(
            chat_id,
            "Commands:\n"
            "/help — this message\n"
            "/status — agent status\n"
            "/memory — list memory\n"
            "/model — list models\n"
            "/model <name> — switch model\n"
            "/ambient — ambient status\n"
            "/ambient on|off — toggle ambient\n"
            "/clear — clear context\n"
            "/reset — factory reset\n"
            "/cancel — cancel active turn",
        )
        return True

    if cmd == "/status":
        mem = memory_engine()
        from core import memory_personality

        core = mem.get_core_profile()
        turn = memory_personality.get_turn()
        lam = memory_personality.lambda_m(turn)
        lines = [
            f"Turn: {turn} (lambda={lam:.3f})",
            f"Core: {core[:80] if core else '(empty)'}",
        ]
        for layer in ("semantic", "episodic", "procedural"):
            count = len(mem.list_entries(layer))
            lines.append(f"{layer.capitalize()}: {count} entries")
        _send(chat_id, "\n".join(lines))
        return True

    if cmd == "/memory":
        mem = memory_engine()
        query = parts[1] if len(parts) > 1 else ""
        if query:
            results = mem.search(query, top_k=10)
            if not results:
                _send(chat_id, f"No results for '{query}'.")
            else:
                lines = [f"Results for '{query}':"]
                for e in results:
                    lines.append(f"[{e.layer}] {e.content[:120]}")
                _send(chat_id, "\n".join(lines))
        else:
            entries = mem.list_entries()
            if not entries:
                _send(chat_id, "Memory is empty.")
            else:
                lines = [f"Memory ({len(entries)} entries):"]
                for e in entries:
                    lines.append(f"[{e.layer[0].upper()}] {e.filename}")
                _send(chat_id, "\n".join(lines))
        return True

    if cmd == "/model":
        from core.proxy import set_model
        from core.providers import list_providers as _list_providers

        if len(parts) > 1:
            try:
                set_model(parts[1].lower())
                _send(chat_id, f"Model set to '{parts[1]}'.")
            except Exception as e:
                _send(chat_id, f"Error: {e}")
        else:
            providers = _list_providers()
            if not providers:
                _send(chat_id, "No providers configured.")
            else:
                _send(chat_id, "Models:\n" + "\n".join(f"  {p}" for p in providers))
        return True

    if cmd == "/ambient":
        from core import memory_store as ms

        cfg = settings.ambient_config()
        action = parts[1].lower() if len(parts) > 1 else ""
        if action == "on":
            settings.set_ambient("enabled", True)
            _send(chat_id, "Ambient agent enabled.")
        elif action == "off":
            settings.set_ambient("enabled", False)
            _send(chat_id, "Ambient agent disabled.")
        elif action == "now":
            _send(chat_id, "Triggering ambient tick...")

            def _do():
                try:
                    result = _run_ambient_tick(force=True)
                except Exception as e:
                    result = f"[ERROR] {e}"
                if result:
                    _send(chat_id, result)
                else:
                    _send(chat_id, "[AMBIENT] (silent)")

            threading.Thread(target=_do, daemon=True).start()
        else:
            count_today = ms.get("ambient.tick_count") or "0"
            tick_date = ms.get("ambient.tick_date") or "-"
            qh = cfg.get("quiet_hours") or [0, 0]
            _send(
                chat_id,
                f"Ambient: {'on' if cfg.get('enabled') else 'off'}\n"
                f"Interval: {cfg.get('interval_minutes')} min\n"
                f"Quiet: {qh[0]:02d}:00-{qh[1]:02d}:00\n"
                f"Today: {count_today}/{cfg.get('max_per_day')} on {tick_date}",
            )
        return True

    if cmd == "/clear":
        p = os.path.join(ROOT, "context.json")
        if os.path.exists(p):
            os.remove(p)
        _send(chat_id, "Context cleared.")
        return True

    if cmd == "/reset":
        _factory_reset()
        _send(chat_id, "Factory reset complete.")
        return True

    if cmd == "/cancel":
        if cancel_active():
            _send(chat_id, "Cancelling...")
        else:
            _send(chat_id, "Nothing to cancel.")
        return True

    return False


def _handle_message(message: dict) -> None:
    text = _extract_text(message)
    chat_id = message.get("chat", {}).get("id")
    user_id = message.get("from", {}).get("id")
    msg_id = message.get("message_id")

    if chat_id is None or user_id is None:
        return

    allowed = _allowed_user_id()
    if allowed is None:
        _send(
            chat_id,
            f"Your user_id: `{user_id}`\n"
            f"Set `telegram_user_id: {user_id}` in config.yaml to unlock.",
        )
        return
    if int(allowed) != int(user_id):
        return

    if text.startswith("/") and _handle_command(chat_id, text):
        return

    global _active_chat_id
    _active_chat_id = chat_id

    file_path = ""
    photo = message.get("photo")
    document = message.get("document")
    if photo:
        largest = max(photo, key=lambda p: p.get("file_size", 0))
        file_path = _download_file(largest["file_id"]) or ""
        if not text:
            text = "[photo]"
    elif document:
        file_id = document.get("file_id")
        file_path = _download_file(file_id) or ""
        file_name = document.get("file_name", "")
        if not text:
            text = f"[document: {file_name}]"

    _send_action(chat_id, "typing")

    def worker():
        stop_typing = threading.Event()

        def typing_heartbeat():
            while not stop_typing.wait(timeout=4):
                _send_action(chat_id, "typing")

        typing_thread = threading.Thread(target=typing_heartbeat, daemon=True)
        typing_thread.start()

        try:
            with _lock:
                response = process(text, file_path=file_path)
        except Exception as e:
            response = f"[SYSTEM ERROR] {e}"
        finally:
            stop_typing.set()
            if file_path and os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

        if response == "[CANCELLED]":
            _send(chat_id, "(cancelled)", reply_to=msg_id)
        else:
            _send(chat_id, response or "(empty)", reply_to=msg_id)

    threading.Thread(target=worker, daemon=True).start()


def _poll_loop() -> None:
    offset = 0
    while True:
        try:
            r = requests.get(
                f"{API}/bot{_token()}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=40,
            )
            data = r.json()
            if not data.get("ok"):
                time.sleep(5)
                continue
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message") or update.get("edited_message")
                if msg:
                    threading.Thread(
                        target=_handle_message, args=(msg,), daemon=True
                    ).start()
        except Exception:
            time.sleep(5)


def _inbox_relay_loop() -> None:
    """Forward inbox messages to the authorized Telegram user."""
    while True:
        time.sleep(2)
        msgs = inbox.drain()
        if not msgs:
            continue
        allowed = _allowed_user_id()
        chat_id = _active_chat_id
        if not allowed:
            continue
        target = chat_id or allowed
        for m in msgs:
            _send(target, f"[inbox] {m}")


def _factory_reset():
    import glob
    import shutil

    for f in (
        "context.json",
        "memory.json",
        "schedule.json",
        "summary.json",
        "settings.json",
    ):
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            os.remove(p)
    functions_dir = os.path.join(ROOT, "core", "functions")
    if os.path.exists(functions_dir):
        for f in glob.glob(os.path.join(functions_dir, "*.py")):
            os.remove(f)
    brain_file = os.path.join(ROOT, "core", "brain.py")
    if os.path.exists(brain_file):
        os.remove(brain_file)
    factory_file = os.path.join(ROOT, "core", "brain_factory.py")
    if os.path.exists(factory_file):
        shutil.copy2(factory_file, brain_file)


def start() -> bool:
    token = _token()
    if not token:
        return False

    threading.Thread(target=_poll_loop, daemon=True).start()
    threading.Thread(target=_inbox_relay_loop, daemon=True).start()

    allowed = _allowed_user_id()
    if allowed:
        inbox.post(f"Telegram bot started (locked to user_id {allowed}).")
    else:
        inbox.post("Telegram bot started (unlocked — will echo user_id to anyone).")
    return True
