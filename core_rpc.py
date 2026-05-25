"""
In-process Core RPC module. Provides the same API surface as the old
brain/core_rpc.py but backed by direct function calls instead of JSON-RPC
over subprocess stdio.

Imported by brain.py and generated functions (including MCP stubs).
"""

import shlex
import subprocess

from core import (
    inbox,
    memory_store,
    proxy,
    scheduler,
    settings,
    mcp_client,
)

_on_event = None
_self_improve_handler = None
_smart_interaction_handler = None


def init(on_event=None, self_improve_handler=None, smart_interaction_handler=None):
    global _on_event, _self_improve_handler, _smart_interaction_handler
    _on_event = on_event
    _self_improve_handler = self_improve_handler
    _smart_interaction_handler = smart_interaction_handler


def event(message: str):
    if _on_event:
        _on_event(str(message))


def self_improve(filename: str, code: str, description: str) -> str:
    if _self_improve_handler is None:
        raise RuntimeError("core_rpc not initialized")
    return _self_improve_handler(
        {
            "filename": filename,
            "code": code,
            "description": description,
        }
    )


def smart_interaction(key: str, label: str, prompt: str, secret: bool = True) -> str:
    if _smart_interaction_handler is None:
        raise RuntimeError("core_rpc not initialized")
    return _smart_interaction_handler(
        {
            "key": key,
            "label": label,
            "prompt": prompt,
            "secret": secret,
        }
    )


class _LLM:
    def __init__(self):
        self.call_count = 0

    def chat(self, messages, tools=None, model=None, timeout=None):
        self.call_count += 1
        kwargs = {"messages": messages}
        if tools is not None:
            kwargs["tools"] = tools
        if model is not None:
            kwargs["model"] = model
        if timeout is not None:
            kwargs["timeout"] = timeout
        if settings.is_auto_route():
            kwargs["auto_route"] = True
        return proxy.chat(**kwargs)

    def reset_count(self):
        self.call_count = 0


llm = _LLM()


class _Inbox:
    def post(self, message: str):
        inbox.post(message)


class _Memory:
    def get(self, key):
        return memory_store.get(key)

    def set(self, key, value):
        memory_store.set(key, value)

    def delete(self, key):
        return memory_store.delete(key)

    def get_all(self):
        return memory_store.get_all()


memory_store = _Memory()


class _Scheduler:
    def add(self, task_id, description, interval_seconds=None, run_at=None):
        return scheduler.add(
            task_id=task_id,
            description=description,
            interval_seconds=interval_seconds,
            run_at=run_at,
        )

    def remove(self, task_id):
        return scheduler.remove(task_id)

    def list_tasks(self):
        return scheduler.list_tasks()


scheduler = _Scheduler()


class _Host:
    def read_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def write_file(self, path, content):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    def run_command(self, cmd):
        cmd_parts = shlex.split(cmd) if isinstance(cmd, str) else cmd
        result = subprocess.run(
            cmd_parts, capture_output=True, text=True, timeout=120
        )
        return {
            "exit": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }


host = _Host()


def mcp_call_tool(server_name: str, tool_name: str, arguments: dict) -> str:
    return mcp_client.call_tool(server_name, tool_name, arguments)


get_initial_input = None
done = None
