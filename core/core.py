import ast
import base64
import json
import mimetypes
import os
import shutil
import datetime
import threading
import time

from core import compressor, context_store, memory_session, runner, scheduler
from core.chat import build_ambient_input, build_input, build_scheduled_input
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

    # Brain.py is protected — functions only
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


def _format_file_attachment(file_path: str) -> str:
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
            return f"[Attached image: {file_name} ({size_str})]\n![{file_name}](data:image/{ext};base64,{b64})"
        except Exception:
            pass

    if mime == "application/pdf":
        try:
            import PyPDF2

            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if text.strip():
                return (
                    f"[Attached PDF: {file_name} ({size_str})]\n```\n{text[:8000]}\n```"
                )
        except Exception:
            pass
        return f"[Attached PDF: {file_name} ({size_str}) — text extraction unavailable]"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        return f"[Attached file: {file_name} ({size_str})]\n```\n{text[:12000]}\n```"
    except UnicodeDecodeError:
        pass

    try:
        with open(file_path, "rb") as f:
            raw = f.read(4096)
        hex_preview = raw[:256].hex()
        return f"[Attached binary file: {file_name} ({size_str}, type: {mime or 'unknown'})]\nHex preview:\n{hex_preview}"
    except Exception:
        return f"[Attached file: {file_name} ({size_str}) — could not read content]"


def process(user_message: str, file_path: str = "", on_event=None) -> str:
    history = context_store.get_all()

    content = user_message
    if file_path and os.path.exists(file_path):
        attachment = _format_file_attachment(file_path)
        if user_message:
            content = f"{user_message}\n\n{attachment}"
        else:
            content = attachment

    mem = memory_engine()
    memory_context = mem.get_relevant_for_prompt(content)
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

    context_store.append("user", content)

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
    if output and not output.startswith("[SYSTEM ERROR]") and output != "[CANCELLED]":
        start_turn_curation(content, output)

    threading.Thread(target=compressor.maybe_compress, daemon=True).start()
    return output


def _make_improve_handler() -> callable:
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


def _run_ambient_tick() -> None:
    mem = memory_engine()
    memory_context = mem.get_relevant_for_prompt("ambient tick")
    messages = build_ambient_input(context_store.get_all(), memory_context)
    output = runner.run_brain_subprocess(
        messages, self_improve_handler=_make_improve_handler()
    )
    if output and not output.startswith("[SYSTEM ERROR]") and output.strip():
        context_store.append("assistant", f"[AMBIENT] {output}")
    elif output.startswith("[SYSTEM ERROR]"):
        context_store.append("system", output)


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


def start_scheduler(interval_check: int = 10, ambient_interval: int = 0) -> None:
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

    if ambient_interval > 0:

        def ambient_loop():
            while True:
                time.sleep(ambient_interval)
                try:
                    _run_ambient_tick()
                except Exception:
                    pass

        threading.Thread(target=ambient_loop, daemon=True).start()
