"""
Brain subprocess manager. Spawns brain/brain.py in its own process, opens a
line-delimited JSON channel over stdio, and dispatches RPC requests via
rpc_server. This is the single seam between Core (host-trusted) and Brain
(sandboxed).

Brain stdout = protocol (init/event/done/rpc_request).
Brain stderr = log lines (forwarded as events with [brain] prefix).
"""

import json
import os
import subprocess
import sys
import threading
import traceback

from core import rpc_server, safety_watchdog

BRAIN_FILE = os.path.join(os.path.dirname(__file__), "..", "brain", "brain.py")
BRAIN_DIR = os.path.dirname(BRAIN_FILE)

_state_lock = threading.Lock()
_active_proc: subprocess.Popen | None = None
_cancelled = False


def cancel_active() -> bool:
    """Kill the currently running brain subprocess, if any. Idempotent.
    Returns True if a process was actually killed."""
    global _cancelled
    with _state_lock:
        proc = _active_proc
        if proc is not None and proc.poll() is None:
            _cancelled = True
            try:
                proc.kill()
            except Exception:
                pass
            return True
    return False


def _consume_cancelled() -> bool:
    """Reads-and-clears the cancelled flag. Called once per turn after the
    subprocess exits, so a subsequent turn starts with a clean slate."""
    global _cancelled
    with _state_lock:
        c = _cancelled
        _cancelled = False
        return c


def _spawn() -> subprocess.Popen:
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    }
    return subprocess.Popen(
        [sys.executable, BRAIN_FILE],
        cwd=BRAIN_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        encoding="utf-8",
        bufsize=1,
    )


def _drain_stderr(proc: subprocess.Popen, on_event, sink: list) -> None:
    for line in proc.stderr:
        line = line.rstrip()
        if not line:
            continue
        sink.append(line)
        if on_event:
            on_event(f"[brain] {line}")


def _send(proc: subprocess.Popen, msg: dict) -> None:
    proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
    proc.stdin.flush()


def _serve(proc: subprocess.Popen, messages: list, on_event, dispatch: dict) -> str:
    _send(proc, {"type": "init", "messages": messages})

    while True:
        line = proc.stdout.readline()
        if not line:
            return "[SYSTEM ERROR] brain subprocess closed channel without 'done'"
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            return f"[SYSTEM ERROR] brain emitted invalid JSON: {e}: {line.strip()[:500]}"

        mtype = msg.get("type")

        if mtype == "done":
            return msg.get("response", "")

        if mtype == "event":
            if on_event:
                on_event(msg.get("message", ""))
            continue

        if mtype == "rpc_request":
            method = msg.get("method")
            handler = dispatch.get(method)
            response = {"type": "rpc_response", "id": msg.get("id")}
            if handler is None:
                response["error"] = f"unknown method '{method}'"
            else:
                try:
                    response["result"] = handler(msg.get("params") or {})
                except Exception as e:
                    response["error"] = f"{type(e).__name__}: {e}"
            _send(proc, response)
            continue

        if on_event:
            on_event(f"[brain] unexpected message type: {mtype}")


def run_brain_subprocess(messages: list, on_event=None, self_improve_handler=None) -> str:
    """Spawn Brain, run one turn, return its 'done' response (or SYSTEM ERROR)."""

    ok, err = safety_watchdog.smoke_test_brain_source(_read_brain_source())
    if not ok:
        if not _try_rollback(f"brain source broken:\n{err}", on_event):
            return f"[SYSTEM ERROR] brain source broken; rollback chain exhausted\n{err}"

    result, exit_code, stderr_tail = _spawn_and_serve(messages, on_event, self_improve_handler)

    if result == "[CANCELLED]":
        return result

    crashed = exit_code != 0 or result.startswith("[SYSTEM ERROR]")
    if not crashed:
        return result

    if not _try_rollback(f"subprocess crashed (exit={exit_code}):\n{stderr_tail}", on_event):
        return f"{result}\nexit={exit_code}\nstderr tail:\n{stderr_tail}"

    result, exit_code, stderr_tail = _spawn_and_serve(messages, on_event, self_improve_handler)
    if exit_code != 0:
        return f"[SYSTEM ERROR] brain crashed again after rollback\nexit={exit_code}\nstderr:\n{stderr_tail}"
    return result


def _spawn_and_serve(messages, on_event, self_improve_handler) -> tuple[str, int, str]:
    global _active_proc
    dispatch = rpc_server.build_dispatch(self_improve_handler)
    proc = _spawn()
    with _state_lock:
        _active_proc = proc

    stderr_lines: list = []
    stderr_thread = threading.Thread(
        target=_drain_stderr, args=(proc, on_event, stderr_lines), daemon=True
    )
    stderr_thread.start()

    try:
        result = _serve(proc, messages, on_event, dispatch)
    except Exception:
        proc.kill()
        result = f"[SYSTEM ERROR] runner exception\n{traceback.format_exc()}"
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        stderr_thread.join(timeout=2)
        with _state_lock:
            _active_proc = None

    if _consume_cancelled():
        return "[CANCELLED]", proc.returncode or 0, ""

    return result, proc.returncode or 0, "\n".join(stderr_lines[-20:])


def _read_brain_source() -> str:
    with open(BRAIN_FILE, "r", encoding="utf-8") as f:
        return f.read()


def _try_rollback(reason: str, on_event) -> bool:
    ok, errors = safety_watchdog.rollback_to_working()
    if ok and on_event:
        on_event(f"[SYSTEM] brain rolled back: {reason}")
    return ok
