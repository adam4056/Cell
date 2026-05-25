"""System function: shell — run a terminal command (permission-gated)."""
import json

SPEC = {
    "description": "Run a shell/terminal command on the host machine. Triggers a permission dialog for the user. Returns exit code, stdout, and stderr. Use this for simple OS operations (open files, list directories, check processes, launch apps) — do NOT self_improve for single commands.",
    "parameters": {
        "type": "object",
        "properties": {
            "cmd": {
                "type": "string",
                "description": "Shell command to execute. On Windows: e.g. 'notepad', 'dir', 'echo hello'. On Unix: e.g. 'ls -la', 'open .'",
            },
        },
        "required": ["cmd"],
    },
}


def run(**kwargs):
    import core_rpc

    cmd = kwargs["cmd"]
    result = core_rpc.host.run_command(cmd)
    return json.dumps(result, ensure_ascii=False)
