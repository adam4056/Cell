import ast
import json
import os
import shutil
import datetime
import threading
import time

from core import compressor, context_store, safety_watchdog, scheduler
from core.chat import build_ambient_input, build_input, build_scheduled_input

BRAIN_FUNCTIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "brain", "functions")
BRAIN_FILE = os.path.join(os.path.dirname(__file__), "..", "brain", "brain.py")
BRAIN_FACTORY_FILE = os.path.join(os.path.dirname(__file__), "..", "brain", "brain_factory.py")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "brain", "backup")

if not os.path.exists(BRAIN_FILE) and os.path.exists(BRAIN_FACTORY_FILE):
    shutil.copy2(BRAIN_FACTORY_FILE, BRAIN_FILE)

def _resolve_self_improve_dest(filename: str) -> tuple[str | None, str]:
    filename = filename.replace("\\", "/").strip()
    if filename == "brain.py" or filename == "brain/brain.py":
        return BRAIN_FILE, "brain.py"

    base = filename
    if base.startswith("brain/"):
        base = base[len("brain/"):]
    if base.startswith("functions/"):
        base = base[len("functions/"):]

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
        return f"[SYSTEM] self_improve rejected: invalid filename '{filename}'. Use 'brain.py' or a flat '<name>.py' (no subdirs, no absolute path)."

    is_brain = dest == BRAIN_FILE

    if is_brain:
        ok, err = safety_watchdog.smoke_test_brain_source(code)
        if not ok:
            return f"[SYSTEM] self_improve rejected: smoke test failed — {err}"

    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    shutil.copy2(BRAIN_FILE, os.path.join(BACKUP_DIR, f"brain_{ts}.py"))
    safety_watchdog.rotate_backups()

    if not is_brain:
        os.makedirs(BRAIN_FUNCTIONS_DIR, exist_ok=True)

    with open(dest, "w", encoding="utf-8") as f:
        f.write(code)

    return f"[SYSTEM] self_improve OK: {resolved} updated. Description: {description}"


def process(user_message: str, on_event=None) -> str:
    history = context_store.get_all()
    messages = build_input(history, user_message)
    context_store.append("user", user_message)

    def handle_improve(args: dict) -> str:
        result = _handle_self_improve(args)
        context_store.append("system", result)
        return result

    output = safety_watchdog.run_brain(messages, on_event=on_event, self_improve_handler=handle_improve)

    if output.startswith("[SYSTEM ERROR]"):
        context_store.append("system", output)
    else:
        context_store.append("assistant", output)

    threading.Thread(target=compressor.maybe_compress, daemon=True).start()
    return output


def _make_improve_handler() -> callable:
    def handle_improve(args: dict) -> str:
        result = _handle_self_improve(args)
        context_store.append("system", result)
        return result
    return handle_improve


def _run_scheduled_task(task: dict) -> None:
    messages = build_scheduled_input(context_store.get_all(), task["description"])
    output = safety_watchdog.run_brain(messages, self_improve_handler=_make_improve_handler())
    if output and not output.startswith("[SYSTEM ERROR]"):
        context_store.append("assistant", f"[SCHEDULED] {output}")
    elif output.startswith("[SYSTEM ERROR]"):
        context_store.append("system", output)


def _run_ambient_tick() -> None:
    messages = build_ambient_input(context_store.get_all())
    output = safety_watchdog.run_brain(messages, self_improve_handler=_make_improve_handler())
    if output and not output.startswith("[SYSTEM ERROR]") and output.strip():
        context_store.append("assistant", f"[AMBIENT] {output}")
    elif output.startswith("[SYSTEM ERROR]"):
        context_store.append("system", output)


def start_scheduler(interval_check: int = 10, ambient_interval: int = 0) -> None:
    def sched_loop():
        while True:
            for task in scheduler.get_due():
                threading.Thread(target=_run_scheduled_task, args=(task,), daemon=True).start()
            time.sleep(interval_check)

    threading.Thread(target=sched_loop, daemon=True).start()

    if ambient_interval > 0:
        def ambient_loop():
            while True:
                time.sleep(ambient_interval)
                try:
                    _run_ambient_tick()
                except Exception:
                    pass

        threading.Thread(target=ambient_loop, daemon=True).start()
