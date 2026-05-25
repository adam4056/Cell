"""Subagent delegation — spawn an isolated agent for a parallel task.

The delegate runs a fresh brain with just the system prompt + task description.
No conversation history, no memory writes. Returns the final text response.
Multiple delegates can run in parallel via threads.
"""
import threading
import time

_result = None
_error = None
_lock = threading.Lock()
_event = threading.Event()


def delegate_task(task: str, timeout: int = 120) -> dict:
    """Run a subagent on a task. Returns {success, result, duration}."""
    global _result, _error
    with _lock:
        _result = None
        _error = None
    _event.clear()

    def worker():
        global _result, _error
        try:
            from core.chat import SYSTEM_PROMPT
            import core_rpc

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"[SUBAGENT TASK — work silently, return only the answer]\n\n{task}"},
            ]
            from core.brain import run as brain_run
            output = brain_run(messages)
            with _lock:
                _result = output
        except Exception as e:
            with _lock:
                _error = str(e)
        finally:
            _event.set()

    t0 = time.time()
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=timeout)

    with _lock:
        if _error:
            return {"success": False, "error": _error, "duration": round(time.time() - t0, 2)}
        if _result is None:
            return {"success": False, "error": "Subagent timed out", "duration": round(time.time() - t0, 2)}
        return {"success": True, "result": _result, "duration": round(time.time() - t0, 2)}
