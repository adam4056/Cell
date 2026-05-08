"""
RPC dispatch table. Maps method names from Brain subprocess to actual Core
module calls. Pure functions — no IO loop here, runner.py owns that.

Methods are registered as `namespace.method` matching the client surface in
`brain/core_rpc.py`. The handler signature is `(params: dict) -> object`.
"""

import subprocess

from core import inbox, memory_store, permissions, proxy, scheduler

try:
    from core import mcp_client

    def _mcp_call_tool(p: dict):
        return mcp_client.call_tool(
            p["server_name"], p["tool_name"], p.get("arguments", {})
        )
except ImportError:

    def _mcp_call_tool(p: dict):
        return "MCP client not available"


def _llm_chat(p: dict):
    kwargs = {"messages": p["messages"]}
    if p.get("tools") is not None:
        kwargs["tools"] = p["tools"]
    if p.get("model") is not None:
        kwargs["model"] = p["model"]
    if p.get("timeout") is not None:
        kwargs["timeout"] = p["timeout"]
    return proxy.chat(**kwargs)


def _inbox_post(p: dict):
    inbox.post(p["message"])
    return None


def _memory_get(p: dict):
    return memory_store.get(p["key"])


def _memory_set(p: dict):
    memory_store.set(p["key"], p["value"])
    return None


def _memory_delete(p: dict):
    return memory_store.delete(p["key"])


def _memory_get_all(p: dict):
    return memory_store.get_all()


def _scheduler_add(p: dict):
    return scheduler.add(
        task_id=p["task_id"],
        description=p["description"],
        interval_seconds=p.get("interval_seconds"),
        run_at=p.get("run_at"),
    )


def _scheduler_remove(p: dict):
    return scheduler.remove(p["task_id"])


def _scheduler_list(p: dict):
    return scheduler.list_tasks()


def _gate(operation: str, detail: str) -> None:
    decision = permissions.request(operation, detail)
    if decision == "allow":
        return
    if decision == "deny":
        raise PermissionError(f"user denied {operation}: {detail}")
    raise PermissionError(
        f"user did not respond to {operation} prompt within timeout: {detail}"
    )


def _host_read_file(p: dict):
    path = p["path"]
    _gate("host.read_file", path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _host_write_file(p: dict):
    path = p["path"]
    _gate("host.write_file", path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(p["content"])
    return True


def _host_run_command(p: dict):
    cmd = p["cmd"]
    _gate("host.run_command", cmd)
    import shlex

    cmd_parts = shlex.split(cmd) if isinstance(cmd, str) else cmd
    result = subprocess.run(cmd_parts, capture_output=True, text=True, timeout=120)
    return {
        "exit": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def build_dispatch(self_improve_handler) -> dict:
    """Build dispatch table. self_improve_handler is bound at runtime
    because it carries the per-turn context_store side effect."""

    def _self_improve(p: dict):
        return self_improve_handler(
            {
                "filename": p["filename"],
                "code": p["code"],
                "description": p["description"],
            }
        )

    return {
        "llm.chat": _llm_chat,
        "self_improve": _self_improve,
        "inbox.post": _inbox_post,
        "memory.get": _memory_get,
        "memory.set": _memory_set,
        "memory.delete": _memory_delete,
        "memory.get_all": _memory_get_all,
        "scheduler.add": _scheduler_add,
        "scheduler.remove": _scheduler_remove,
        "scheduler.list_tasks": _scheduler_list,
        "host.read_file": _host_read_file,
        "host.write_file": _host_write_file,
        "host.run_command": _host_run_command,
        "mcp.call_tool": _mcp_call_tool,
    }
