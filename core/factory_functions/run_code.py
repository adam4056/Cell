"""System function: run_code — execute Python in an isolated sandbox."""
import json

SPEC = {
    "description": "Execute Python code in an isolated sandbox environment. Dependencies can be installed on-the-fly via the packages parameter. Returns stdout, stderr, and exit code. Use this for calculations, data processing, testing code, or any Python execution needed to complete a task.",
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python source code to execute",
            },
            "packages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of pip packages to install before running (e.g. ['requests', 'numpy'])",
            },
            "timeout": {
                "type": "integer",
                "description": "Execution timeout in seconds (default 60)",
            },
        },
        "required": ["code"],
    },
}


def run(**kwargs):
    from core.sandbox import run_code

    result = run_code(
        kwargs["code"],
        packages=kwargs.get("packages"),
        timeout=kwargs.get("timeout", 60),
    )
    return json.dumps(result, ensure_ascii=False)
