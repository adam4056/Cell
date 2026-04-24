import subprocess
import shlex

ALLOWED_COMMANDS = {"python", "python3", "pip", "ls", "dir", "cat", "type", "echo", "pwd"}
MAX_OUTPUT = 4000


def execute(command: str) -> str:
    try:
        parts = shlex.split(command)
    except ValueError as e:
        return f"[SHELL ERROR] invalid command: {e}"

    if not parts:
        return "[SHELL ERROR] empty command"

    base = parts[0].lower().rstrip(".exe")
    if base not in ALLOWED_COMMANDS:
        return f"[SHELL DENIED] '{parts[0]}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}"

    try:
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = result.stdout + result.stderr
        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT] + "\n[... truncated]"
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "[SHELL ERROR] command timed out (15s)"
    except Exception as e:
        return f"[SHELL ERROR] {e}"
