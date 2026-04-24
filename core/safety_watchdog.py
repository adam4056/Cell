import inspect
import shutil
import subprocess
import sys
import tempfile
import traceback
import os
import importlib.util

BRAIN_FILE = os.path.join(os.path.dirname(__file__), "..", "brain", "brain.py")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "brain", "backup")
CELL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MAX_BACKUPS = 20
MAX_ROLLBACK_ATTEMPTS = 3
SMOKE_TEST_TIMEOUT = 10


def smoke_test_brain_source(code: str) -> tuple[bool, str]:
    fd, tmp = tempfile.mkstemp(suffix=".py", prefix="brain_smoke_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    probe = (
        "import importlib.util, sys;"
        f"spec = importlib.util.spec_from_file_location('brain_smoke', r'{tmp}');"
        "m = importlib.util.module_from_spec(spec);"
        "spec.loader.exec_module(m);"
        "assert hasattr(m, 'run') and callable(m.run), 'missing run()';"
        "print('OK')"
    )
    env = {**os.environ, "PYTHONPATH": CELL_ROOT + os.pathsep + os.environ.get("PYTHONPATH", "")}
    try:
        result = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True, text=True, timeout=SMOKE_TEST_TIMEOUT, env=env,
        )
    except subprocess.TimeoutExpired:
        return False, f"smoke test timed out ({SMOKE_TEST_TIMEOUT}s)"
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    if result.returncode == 0:
        return True, ""
    return False, (result.stderr or result.stdout).strip()[:2000]


def _backups_newest_first() -> list:
    if not os.path.exists(BACKUP_DIR):
        return []
    return [os.path.join(BACKUP_DIR, f) for f in sorted(os.listdir(BACKUP_DIR), reverse=True)]


def rotate_backups() -> None:
    backups = _backups_newest_first()
    for old in backups[MAX_BACKUPS:]:
        try:
            os.remove(old)
        except OSError:
            pass


def _try_load() -> tuple[object | None, str | None]:
    try:
        spec = importlib.util.spec_from_file_location("brain", BRAIN_FILE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, None
    except Exception:
        return None, traceback.format_exc()


def _invoke_run(module, context, on_event, self_improve_handler=None):
    try:
        params = inspect.signature(module.run).parameters
    except (TypeError, ValueError):
        return module.run(context, on_event=on_event)
    kwargs = {}
    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    if "on_event" in params or has_var_kw:
        kwargs["on_event"] = on_event
    if "self_improve_handler" in params or has_var_kw:
        kwargs["self_improve_handler"] = self_improve_handler
    return module.run(context, **kwargs)


def _rollback_chain() -> tuple[object | None, list]:
    errors = []
    for candidate in _backups_newest_first()[:MAX_ROLLBACK_ATTEMPTS]:
        shutil.copy2(candidate, BRAIN_FILE)
        module, err = _try_load()
        if module is not None:
            return module, errors
        errors.append((candidate, err))
    return None, errors


def run_brain(context: list, on_event=None, self_improve_handler=None) -> str:
    module, load_err = _try_load()
    if module is None:
        recovered, chain_errors = _rollback_chain()
        if recovered is None:
            trail = "\n---\n".join(f"{os.path.basename(p)}:\n{e}" for p, e in chain_errors)
            return f"[SYSTEM ERROR] brain load failed; rollback chain exhausted\nOriginal:\n{load_err}\n\nRollback attempts:\n{trail}"
        module = recovered
        rollback_note = f"[SYSTEM] brain rolled back due to load error:\n{load_err}"
        if on_event:
            on_event(rollback_note)

    try:
        return _invoke_run(module, context, on_event, self_improve_handler)
    except (ImportError, AttributeError, TypeError, SyntaxError, NameError):
        run_err = traceback.format_exc()
        recovered, chain_errors = _rollback_chain()
        if recovered is None:
            trail = "\n---\n".join(f"{os.path.basename(p)}:\n{e}" for p, e in chain_errors)
            return f"[SYSTEM ERROR] brain run broken; rollback chain exhausted\nOriginal:\n{run_err}\n\nRollback attempts:\n{trail}"
        if on_event:
            on_event(f"[SYSTEM] brain rolled back due to broken run:\n{run_err}")
        try:
            return _invoke_run(recovered, context, on_event, self_improve_handler)
        except Exception:
            return f"[SYSTEM ERROR] brain run exception after rollback\n{traceback.format_exc()}"
    except Exception:
        return f"[SYSTEM ERROR] brain run exception\n{traceback.format_exc()}"
