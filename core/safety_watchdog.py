import ast
import shutil
import subprocess
import sys
import tempfile
import os

BRAIN_FILE = os.path.join(os.path.dirname(__file__), "..", "brain", "brain.py")
BRAIN_DIR = os.path.dirname(BRAIN_FILE)
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "brain", "backup")
CELL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MAX_BACKUPS = 20
MAX_ROLLBACK_ATTEMPTS = 3
SMOKE_TEST_TIMEOUT = 10


def _has_main_guard(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        cmp = node.test
        if not isinstance(cmp, ast.Compare):
            continue
        left = cmp.left
        if isinstance(left, ast.Name) and left.id == "__name__":
            return True
        if cmp.comparators and isinstance(cmp.comparators[0], ast.Name) and cmp.comparators[0].id == "__name__":
            return True
    return False


def smoke_test_brain_source(code: str) -> tuple[bool, str]:
    if not _has_main_guard(code):
        return False, "missing `if __name__ == '__main__':` block — brain.py must be runnable as a script"
    # Write the smoke probe inside brain/ so the candidate's own
    # `sys.path.insert(0, dirname(__file__))` resolves `core_rpc`.
    fd, tmp = tempfile.mkstemp(suffix=".py", prefix="brain_smoke_", dir=BRAIN_DIR)
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


def rollback_to_working() -> tuple[bool, list]:
    """Restore the newest backup that passes smoke test. Returns (ok, errors)."""
    errors = []
    for candidate in _backups_newest_first()[:MAX_ROLLBACK_ATTEMPTS]:
        with open(candidate, "r", encoding="utf-8") as f:
            code = f.read()
        ok, err = smoke_test_brain_source(code)
        if not ok:
            errors.append((candidate, err))
            continue
        shutil.copy2(candidate, BRAIN_FILE)
        return True, errors
    return False, errors
