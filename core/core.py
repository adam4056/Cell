import ast
import base64
import json
import mimetypes
import os
import shutil
import datetime
import threading
import time

from core import (
    chats_store,
    compressor,
    context_store,
    memory_session,
    memory_store,
    runner,
    scheduler,
    settings,
)
from core.chat import (
    build_ambient_input,
    build_input,
    build_scheduled_input,
    record_user_activity_pattern,
)
from core.memory_engine import engine as memory_engine
from core.memory_curator import start_session_curation, start_turn_curation

BRAIN_FUNCTIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "brain", "functions"
)
BRAIN_FILE = os.path.join(os.path.dirname(__file__), "..", "brain", "brain.py")
BRAIN_FACTORY_FILE = os.path.join(
    os.path.dirname(__file__), "..", "brain", "brain_factory.py"
)
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "brain", "backup")

if not os.path.exists(BRAIN_FILE) and os.path.exists(BRAIN_FACTORY_FILE):
    shutil.copy2(BRAIN_FACTORY_FILE, BRAIN_FILE)


def _resolve_self_improve_dest(filename: str) -> tuple[str | None, str]:
    filename = filename.replace("\\", "/").strip()

    if filename == "brain.py" or filename == "brain/brain.py":
        return None, "brain.py"

    base = filename
    if base.startswith("brain/"):
        base = base[len("brain/") :]
    if base.startswith("functions/"):
        base = base[len("functions/") :]

    if "/" in base or ".." in base or os.path.isabs(base):
        return None, base
    if not base.endswith(".py"):
        return None, base
    if base == "__init__.py":
        return None, base

    return os.path.join(BRAIN_FUNCTIONS_DIR, base), base


def _handle_self_improve(args: dict) -> str:
    filename = args["filename"]
    code = args["code"]
    description = args["description"]

    try:
        ast.parse(code)
    except SyntaxError as e:
        return f"[SYSTEM] self_improve rejected: syntax error — {e}"

    dest, resolved = _resolve_self_improve_dest(filename)
    if dest is None:
        return f"[SYSTEM] self_improve rejected: invalid filename '{filename}'. Functions only — write a flat '<name>.py' (no subdirs, no absolute path). Rewriting brain.py is not allowed."

    os.makedirs(BRAIN_FUNCTIONS_DIR, exist_ok=True)

    with open(dest, "w", encoding="utf-8") as f:
        f.write(code)

    return f"[SYSTEM] self_improve OK: {resolved} created. Description: {description}"


def _format_file_attachment(file_path: str) -> dict:
    file_name = os.path.basename(file_path)
    mime, _ = mimetypes.guess_type(file_path)
    size = os.path.getsize(file_path)
    size_str = (
        f"{size / 1024:.1f} KB"
        if size < 1024 * 1024
        else f"{size / (1024 * 1024):.1f} MB"
    )

    image_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
    is_image = (
        mime
        and mime.startswith("image/")
        or os.path.splitext(file_path)[1].lower() in image_exts
    )

    if is_image:
        try:
            with open(file_path, "rb") as f:
                img_bytes = f.read()
            b64 = base64.b64encode(img_bytes).decode("ascii")
            ext = os.path.splitext(file_path)[1].lower().lstrip(".") or "png"
            img_mime = mime or f"image/{ext}"
            return {
                "text": f"[Attached image: {file_name} ({size_str})]",
                "images": [{"mime_type": img_mime, "base64": b64}],
            }
        except Exception:
            pass

    if mime == "application/pdf":
        try:
            import PyPDF2

            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if text.strip():
                return {
                    "text": f"[Attached PDF: {file_name} ({size_str})]\n```\n{text[:8000]}\n```"
                }
        except Exception:
            pass
        return {
            "text": f"[Attached PDF: {file_name} ({size_str}) — text extraction unavailable]"
        }

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        return {
            "text": f"[Attached file: {file_name} ({size_str})]\n```\n{text[:12000]}\n```"
        }
    except UnicodeDecodeError:
        pass

    try:
        with open(file_path, "rb") as f:
            raw = f.read(4096)
        hex_preview = raw[:256].hex()
        return {
            "text": f"[Attached binary file: {file_name} ({size_str}, type: {mime or 'unknown'})]\nHex preview:\n{hex_preview}"
        }
    except Exception:
        return {
            "text": f"[Attached file: {file_name} ({size_str}) — could not read content]"
        }


def _extract_text_from_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content)


def _build_user_content(user_message: str, attachment: dict | None) -> str | list:
    if attachment is None:
        return user_message
    text = attachment.get("text", "")
    images = attachment.get("images", [])
    body = f"{user_message}\n\n{text}" if user_message else text

    if not images:
        return body

    blocks = [{"type": "text", "text": body}]
    for img in images:
        mime = img.get("mime_type", "image/png")
        b64 = img.get("base64", "")
        blocks.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            }
        )
    return blocks


def process(user_message: str, file_path: str = "", on_event=None) -> str:
    history = context_store.get_all()

    attachment = None
    if file_path and os.path.exists(file_path):
        attachment = _format_file_attachment(file_path)
    content = _build_user_content(user_message, attachment)

    mem = memory_engine()
    memory_context = mem.get_relevant_for_prompt(_extract_text_from_content(content))
    messages = build_input(history, content, memory_context)

    # Mark a new user turn for the session tracker. If the previous session
    # idled out, close it now and dispatch its dialogue to the session curator
    # before this turn's messages get appended.
    pre_turn_offset = len(history)
    _, just_closed = memory_session.touch(message_offset=pre_turn_offset)
    if just_closed is not None:
        offset = int(just_closed.get("message_offset", 0))
        end = pre_turn_offset
        session_msgs = history[offset:end]
        start_session_curation(just_closed, session_msgs)

    context_store.append("user", _extract_text_from_content(content))
    memory_store.set("ambient.last_user_ts", str(time.time()))
    record_user_activity_pattern()

    def handle_improve(args: dict) -> str:
        result = _handle_self_improve(args)
        context_store.append("system", result)
        return result

    output = runner.run_brain_subprocess(
        messages, on_event=on_event, self_improve_handler=handle_improve
    )

    if output == "[CANCELLED]":
        context_store.append("system", "(response cancelled)")
    elif output.startswith("[SYSTEM ERROR]"):
        context_store.append("system", output)
    else:
        context_store.append("assistant", output)

    # Phase 2 (per-turn): semantic facts + personality EMA.
    # Skip curation for trivially short messages to save tokens.
    if output and not output.startswith("[SYSTEM ERROR]") and output != "[CANCELLED]":
        combined_len = len(_extract_text_from_content(content)) + len(output)
        if combined_len > 60:
            start_turn_curation(_extract_text_from_content(content), output)

    threading.Thread(target=compressor.maybe_compress, daemon=True).start()
    return output


def process_chat(
    chat_id: str, user_message: str, file_path: str = "", on_event=None
) -> str:
    """Run a turn against an isolated chat. No memory curation, no context_store.

    Reads memory for retrieval (Cell still knows the user) but doesn't write back.
    """
    chat = chats_store.get(chat_id)
    if chat is None:
        return f"[SYSTEM ERROR] chat not found: {chat_id}"

    attachment = None
    if file_path and os.path.exists(file_path):
        attachment = _format_file_attachment(file_path)
    content = _build_user_content(user_message, attachment)

    history = chat.get("history", [])
    mem = memory_engine()
    memory_context = mem.get_relevant_for_prompt(_extract_text_from_content(content))
    messages = build_input(history, content, memory_context)

    chats_store.append(chat_id, "user", _extract_text_from_content(content))
    if (
        not history
        and not chat.get("title", "").strip()
        or chat.get("title") == "New chat"
    ):
        title = user_message.strip().split("\n")[0][:60] or "New chat"
        chats_store.set_title(chat_id, title)

    output = runner.run_brain_subprocess(
        messages,
        on_event=on_event,
        self_improve_handler=_make_improve_handler(chat_id=chat_id),
    )

    if output == "[CANCELLED]":
        chats_store.append(chat_id, "system", "(response cancelled)")
    elif output.startswith("[SYSTEM ERROR]"):
        chats_store.append(chat_id, "system", output)
    else:
        chats_store.append(chat_id, "assistant", output)

    return output


def _make_improve_handler(chat_id: str | None = None) -> callable:
    if chat_id:

        def handle_improve(args: dict) -> str:
            result = _handle_self_improve(args)
            chats_store.append(chat_id, "system", result)
            return result
    else:

        def handle_improve(args: dict) -> str:
            result = _handle_self_improve(args)
            context_store.append("system", result)
            return result

    return handle_improve


def _run_scheduled_task(task: dict) -> None:
    mem = memory_engine()
    memory_context = mem.get_relevant_for_prompt(task["description"])
    messages = build_scheduled_input(
        context_store.get_all(), task["description"], memory_context
    )
    output = runner.run_brain_subprocess(
        messages, self_improve_handler=_make_improve_handler()
    )
    if output and not output.startswith("[SYSTEM ERROR]"):
        context_store.append("assistant", f"[SCHEDULED] {output}")
    elif output.startswith("[SYSTEM ERROR]"):
        context_store.append("system", output)


def _in_quiet_hours(now: datetime.datetime, start: int, end: int) -> bool:
    if start == end:
        return False
    h = now.hour
    if start < end:
        return start <= h < end
    return h >= start or h < end


def _ambient_skip_reason(cfg: dict, force: bool = False) -> str | None:
    """Return a reason string if this tick should be skipped, else None."""
    if force:
        return None
    if not cfg.get("enabled", False):
        return "ambient disabled"

    now = datetime.datetime.now()
    qh = cfg.get("quiet_hours") or [0, 0]
    if (
        isinstance(qh, list)
        and len(qh) == 2
        and _in_quiet_hours(now, int(qh[0]), int(qh[1]))
    ):
        return f"quiet hours {qh[0]:02d}-{qh[1]:02d}"

    cooldown_s = int(cfg.get("cooldown_after_user_min", 5)) * 60
    last_user = memory_store.get("ambient.last_user_ts")
    try:
        if last_user and time.time() - float(last_user) < cooldown_s:
            return "user active recently"
    except (TypeError, ValueError):
        pass

    today = now.strftime("%Y-%m-%d")
    count_date = memory_store.get("ambient.tick_date")
    try:
        count = int(memory_store.get("ambient.tick_count") or "0")
    except (TypeError, ValueError):
        count = 0
    if count_date == today and count >= int(cfg.get("max_per_day", 6)):
        return f"daily cap reached ({count})"
    return None


def _record_ambient_tick() -> None:
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    count_date = memory_store.get("ambient.tick_date")
    try:
        count = int(memory_store.get("ambient.tick_count") or "0")
    except (TypeError, ValueError):
        count = 0
    if count_date != today:
        count = 0
    memory_store.set("ambient.tick_date", today)
    memory_store.set("ambient.tick_count", str(count + 1))
    memory_store.set("ambient.last_tick_ts", str(time.time()))


def _run_ambient_tick(force: bool = False) -> str | None:
    cfg = settings.ambient_config()
    skip = _ambient_skip_reason(cfg, force=force)
    if skip:
        return f"[AMBIENT skipped] {skip}"

    _record_ambient_tick()

    mem = memory_engine()
    memory_context = mem.get_relevant_for_prompt("ambient tick")
    messages = build_ambient_input(context_store.get_all(), memory_context)
    output = runner.run_brain_subprocess(
        messages, self_improve_handler=_make_improve_handler()
    )
    if output and not output.startswith("[SYSTEM ERROR]") and output.strip():
        context_store.append("assistant", f"[AMBIENT] {output}")
    elif output and output.startswith("[SYSTEM ERROR]"):
        context_store.append("system", output)
    return output


def _check_session_idle() -> None:
    """If the active session has idled past the timeout, close + curate it."""
    if not memory_session.is_idle_expired():
        return
    closed = memory_session.finalize(reason="idle_timeout")
    if not closed:
        return
    history = context_store.get_all()
    offset = int(closed.get("message_offset", 0))
    session_msgs = history[offset:]
    start_session_curation(closed, session_msgs)


def start_scheduler(
    interval_check: int = 10, ambient_interval: int | None = None
) -> None:
    def sched_loop():
        while True:
            for task in scheduler.get_due():
                threading.Thread(
                    target=_run_scheduled_task, args=(task,), daemon=True
                ).start()
            time.sleep(interval_check)

    threading.Thread(target=sched_loop, daemon=True).start()

    def session_idle_loop():
        while True:
            time.sleep(60)
            try:
                _check_session_idle()
            except Exception:
                pass

    threading.Thread(target=session_idle_loop, daemon=True).start()

    # Ambient loop runs unconditionally and re-reads config each tick, so the
    # user can flip ambient.enabled at runtime without restart. The skip-guard
    # short-circuits when disabled or in cooldown/quiet/over-cap.
    def ambient_loop():
        while True:
            cfg = settings.ambient_config()
            interval_s = max(60, int(cfg.get("interval_minutes", 30)) * 60)
            if ambient_interval is not None and ambient_interval > 0:
                interval_s = ambient_interval
            time.sleep(interval_s)
            try:
                _run_ambient_tick()
            except Exception:
                pass

    threading.Thread(target=ambient_loop, daemon=True).start()
