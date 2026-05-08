"""
Core-RPC client. The single channel through which Brain talks to Core (and
therefore to the host OS / network / persistence). Every operation that has
side-effects outside Brain's own subprocess goes through this module.

Protocol: line-delimited JSON over stdio. Brain writes to stdout, reads from
stdin. Brain's *own* prints/logs are redirected to stderr at import time so
they cannot corrupt the protocol.
"""

import sys
import json
import threading

# Capture the real stdout BEFORE redirecting; protocol writes go here.
_protocol_out = sys.stdout
_protocol_in = sys.stdin

# Anything Brain accidentally prints during normal execution must NOT pollute
# the protocol channel — push it to stderr (Core captures it as log lines).
sys.stdout = sys.stderr

_lock = threading.Lock()
_id_counter = 0


def _next_id() -> str:
    global _id_counter
    _id_counter += 1
    return str(_id_counter)


def _send(msg: dict) -> None:
    _protocol_out.write(json.dumps(msg, ensure_ascii=False) + "\n")
    _protocol_out.flush()


def _read() -> dict:
    line = _protocol_in.readline()
    if not line:
        raise RuntimeError("core_rpc: Core closed the channel")
    return json.loads(line)


def _call(method: str, **params) -> object:
    with _lock:
        rid = _next_id()
        _send({"type": "rpc_request", "id": rid, "method": method, "params": params})
        while True:
            msg = _read()
            if msg.get("type") == "rpc_response" and msg.get("id") == rid:
                if msg.get("error"):
                    raise RuntimeError(f"core_rpc {method}: {msg['error']}")
                return msg.get("result")


def get_initial_input() -> dict:
    msg = _read()
    if msg.get("type") != "init":
        raise RuntimeError(f"core_rpc: expected init, got {msg.get('type')}")
    return msg


def event(message: str) -> None:
    """Streaming progress notification — non-blocking, no response expected."""
    _send({"type": "event", "message": str(message)})


def done(response: str) -> None:
    """Signal end of turn. After this, Brain should exit."""
    _send({"type": "done", "response": str(response)})


# --- LLM ---


class _LLM:
    def chat(self, messages, tools=None, model=None, timeout=None):
        params = {"messages": messages}
        if tools is not None:
            params["tools"] = tools
        if model is not None:
            params["model"] = model
        if timeout is not None:
            params["timeout"] = timeout
        return _call("llm.chat", **params)


llm = _LLM()


# --- Self-improve ---


def self_improve(filename: str, code: str, description: str) -> str:
    return _call("self_improve", filename=filename, code=code, description=description)


# --- MCP ---


def mcp_call_tool(server_name: str, tool_name: str, arguments: dict) -> str:
    return _call(
        "mcp.call_tool",
        server_name=server_name,
        tool_name=tool_name,
        arguments=arguments,
    )


# --- Inbox ---


class _Inbox:
    def post(self, message: str) -> None:
        _call("inbox.post", message=message)


inbox = _Inbox()


# --- Memory ---


class _Memory:
    def get(self, key: str):
        return _call("memory.get", key=key)

    def set(self, key: str, value: str) -> None:
        _call("memory.set", key=key, value=value)

    def delete(self, key: str) -> bool:
        return _call("memory.delete", key=key)

    def get_all(self) -> dict:
        return _call("memory.get_all")


memory_store = _Memory()


# --- Scheduler ---


class _Scheduler:
    def add(self, task_id, description, interval_seconds=None, run_at=None):
        return _call(
            "scheduler.add",
            task_id=task_id,
            description=description,
            interval_seconds=interval_seconds,
            run_at=run_at,
        )

    def remove(self, task_id):
        return _call("scheduler.remove", task_id=task_id)

    def list_tasks(self):
        return _call("scheduler.list_tasks")


scheduler = _Scheduler()


# --- Host (gated by user permission dialog in Core) ---


class _Host:
    def read_file(self, path: str) -> str:
        return _call("host.read_file", path=path)

    def write_file(self, path: str, content: str) -> bool:
        return _call("host.write_file", path=path, content=content)

    def run_command(self, cmd: str) -> dict:
        return _call("host.run_command", cmd=cmd)


host = _Host()
