"""
In-process brain runner. Previously spawned brain.py as a subprocess with
JSON-RPC over stdio. Now imports brain directly and calls it in-process.

The `event` and `self_improve` callbacks are threaded through core_rpc.init()
so that brain.py and generated functions can access them without the subprocess
protocol.
"""

import threading
import traceback
import os
import shutil

from core import brain_factory as brain_factory_module, safety_watchdog
from core.brain import run as brain_run
import core_rpc

BRAIN_FILE = os.path.join(os.path.dirname(__file__), "brain.py")
BRAIN_FACTORY_FILE = os.path.join(os.path.dirname(__file__), "brain_factory.py")

_lock = threading.Lock()
_running = False
_cancelled = False


def cancel_active() -> bool:
    global _cancelled
    with _lock:
        if _running:
            _cancelled = True
            return True
    return False


def _restore_from_factory(on_event) -> tuple[bool, str]:
    if not os.path.exists(BRAIN_FACTORY_FILE):
        return False, "brain factory file not found"
    try:
        with open(BRAIN_FACTORY_FILE, "r", encoding="utf-8") as f:
            code = f.read()
        ok, err = safety_watchdog.smoke_test_brain_source(code)
        if not ok:
            return False, f"brain factory fails smoke test: {err}"
        shutil.copy2(BRAIN_FACTORY_FILE, BRAIN_FILE)
        if on_event:
            on_event("[SYSTEM] brain restored from factory")
        return True, ""
    except Exception as e:
        return False, f"brain factory restoration failed: {e}"


def run_brain_subprocess(
    messages: list, on_event=None, smart_interaction_handler=None
) -> str:
    global _running, _cancelled

    ok, err = safety_watchdog.smoke_test_brain_source(_read_brain_source())
    if not ok:
        restored, restore_err = _restore_from_factory(on_event)
        if not restored:
            return f"[SYSTEM ERROR] brain source broken; factory restore failed\nsmoke: {err}\nrestore: {restore_err}"

    with _lock:
        _running = True
        _cancelled = False

    core_rpc.init(
        on_event=on_event,
        smart_interaction_handler=smart_interaction_handler,
    )

    try:
        result = brain_run(messages)
    except Exception:
        result = f"[SYSTEM ERROR] brain run exception\n{traceback.format_exc()}"
    finally:
        with _lock:
            _running = False
            was_cancelled = _cancelled
            _cancelled = False

    if was_cancelled:
        return "[CANCELLED]"

    return result


def _read_brain_source() -> str:
    with open(BRAIN_FILE, "r", encoding="utf-8") as f:
        return f.read()
