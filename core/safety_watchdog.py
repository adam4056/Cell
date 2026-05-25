import ast
import os

BRAIN_FILE = os.path.join(os.path.dirname(__file__), "brain.py")
BRAIN_DIR = os.path.dirname(BRAIN_FILE)
CELL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_last_brain_mtime = 0
_last_brain_result = (True, "")


def smoke_test_brain_source(code: str) -> tuple[bool, str]:
    global _last_brain_mtime, _last_brain_result
    try:
        mtime = os.path.getmtime(BRAIN_FILE)
    except OSError:
        mtime = 0
    if mtime == _last_brain_mtime:
        return _last_brain_result
    ok, err = _validate(code)
    _last_brain_mtime = mtime
    _last_brain_result = (ok, err)
    return ok, err


def _validate(code: str) -> tuple[bool, str]:
    if not _has_run_function(code):
        return False, "missing `def run(` — brain module must define run()"
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, f"syntax error: {e}"
    return True, ""


def smoke_test_function_source(code: str) -> tuple[bool, str]:
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, f"syntax error: {e}"
    return True, ""


def _has_run_function(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run":
            return True
    return False
