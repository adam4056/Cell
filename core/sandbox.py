"""Cell Code Sandbox — Safe execution of user/agent code.

Creates isolated venv, runs code, captures output, cleans up.
Used by brain functions to test code before deployment.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()

SANDBOX_DIR = os.path.join(os.path.dirname(__file__), "..", "sandbox")
os.makedirs(SANDBOX_DIR, exist_ok=True)


def _ensure_venv(sandbox_path: str) -> str:
    """Create venv if it doesn't exist."""
    venv_path = os.path.join(sandbox_path, ".venv")
    if os.path.exists(os.path.join(venv_path, "bin", "python")) or os.path.exists(
        os.path.join(venv_path, "Scripts", "python.exe")
    ):
        return venv_path
    subprocess.run(
        [sys.executable, "-m", "venv", venv_path], check=True, capture_output=True
    )
    return venv_path


def _get_python(venv_path: str) -> str:
    """Get python executable from venv."""
    if os.name == "nt":
        return os.path.join(venv_path, "Scripts", "python.exe")
    return os.path.join(venv_path, "bin", "python")


def _get_pip(venv_path: str) -> str:
    """Get pip executable from venv."""
    if os.name == "nt":
        return os.path.join(venv_path, "Scripts", "pip.exe")
    return os.path.join(venv_path, "bin", "pip")


class CodeSandbox:
    """Isolated code execution environment."""

    def __init__(self, sandbox_id: str | None = None) -> None:
        self.id = sandbox_id or str(uuid.uuid4())[:8]
        self.path = os.path.join(SANDBOX_DIR, self.id)
        os.makedirs(self.path, exist_ok=True)
        self.venv = _ensure_venv(self.path)
        self.python = _get_python(self.venv)
        self.pip = _get_pip(self.venv)

    def install(self, packages: list[str]) -> tuple[bool, str]:
        """Install packages into sandbox venv."""
        if not packages:
            return True, ""
        try:
            result = subprocess.run(
                [self.pip, "install"] + packages,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                return True, result.stdout[-500:]
            return False, result.stderr[-1000:]
        except subprocess.TimeoutExpired:
            return False, "pip install timed out"
        except Exception as e:
            return False, str(e)

    def run(self, code: str, timeout: int = 60) -> dict[str, Any]:
        """Run Python code in sandbox."""
        script_path = os.path.join(self.path, "script.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        try:
            result = subprocess.run(
                [self.python, script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.path,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout}s",
                "returncode": -1,
            }
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}

    def run_file(self, file_path: str, timeout: int = 60) -> dict[str, Any]:
        """Run existing Python file in sandbox."""
        if not os.path.exists(file_path):
            return {
                "success": False,
                "stdout": "",
                "stderr": f"File not found: {file_path}",
                "returncode": -1,
            }
        try:
            result = subprocess.run(
                [self.python, file_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.path,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout}s",
                "returncode": -1,
            }
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}

    def cleanup(self) -> None:
        """Remove sandbox directory."""
        if os.path.exists(self.path):
            shutil.rmtree(self.path)

    def __enter__(self) -> "CodeSandbox":
        return self

    def __exit__(self, *args: Any) -> None:
        self.cleanup()


# Convenience function
def run_code(
    code: str, packages: list[str] | None = None, timeout: int = 60
) -> dict[str, Any]:
    """One-shot code execution."""
    with CodeSandbox() as sandbox:
        if packages:
            ok, err = sandbox.install(packages)
            if not ok:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Package install failed: {err}",
                    "returncode": -1,
                }
        return sandbox.run(code, timeout=timeout)
