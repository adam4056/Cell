import sys
import os
import io
import contextlib
import importlib.util
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import proxy

FUNCTIONS_DIR = os.path.join(os.path.dirname(__file__), "functions")
MAX_ITERATIONS = 25

SELF_IMPROVE_TOOL = {
    "type": "function",
    "function": {
        "name": "self_improve",
        "description": "Create or modify a file. Use filename='brain.py' to rewrite core logic, or a flat filename like 'get_weather.py' for a new capability (saved into brain/functions/). Never include a directory prefix. Function files must define run(**kwargs) and a SPEC dict where SPEC['parameters'] is a JSON Schema object: {'type':'object','properties':{...},'required':[...]}.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Flat filename, e.g. 'get_weather.py' or 'brain.py'. No subdirectory."},
                "description": {"type": "string"},
                "code": {"type": "string", "description": "Full Python source. Must define run(**kwargs) and SPEC dict."},
            },
            "required": ["filename", "description", "code"],
        },
    },
}


def _normalize_spec(spec: dict) -> dict:
    spec = dict(spec)
    params = spec.get("parameters")
    if params is None:
        spec["parameters"] = {"type": "object", "properties": {}}
    elif not isinstance(params, dict):
        spec["parameters"] = {"type": "object", "properties": {}}
    elif params.get("type") != "object":
        spec["parameters"] = {"type": "object", "properties": params}
    elif "properties" not in params:
        params["properties"] = {}
        spec["parameters"] = params
    return spec


def _load_functions() -> tuple[list, dict]:
    tools = []
    modules = {}
    if not os.path.exists(FUNCTIONS_DIR):
        return tools, modules
    for fname in os.listdir(FUNCTIONS_DIR):
        if not fname.endswith(".py"):
            continue
        path = os.path.join(FUNCTIONS_DIR, fname)
        spec = importlib.util.spec_from_file_location(fname[:-3], path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            continue
        if hasattr(mod, "SPEC") and hasattr(mod, "run"):
            normalized = _normalize_spec({**mod.SPEC, "name": fname[:-3]})
            tools.append({"type": "function", "function": normalized})
            modules[fname[:-3]] = mod
    return tools, modules


def run(context: list, on_event=None, self_improve_handler=None) -> str:
    dyn_tools, modules = _load_functions()
    tools = [SELF_IMPROVE_TOOL] + dyn_tools
    messages = list(context)

    def emit(msg):
        if on_event:
            on_event(msg)

    for iteration in range(1, MAX_ITERATIONS + 1):
        message = proxy.chat(messages, tools=tools)
        emit(f"⏱ llm call #{iteration}")

        if not message.get("tool_calls"):
            return message.get("content", "")

        messages.append(message)

        did_self_improve = False

        for call in message["tool_calls"]:
            name = call["function"]["name"]
            args = json.loads(call["function"]["arguments"])

            if name == "self_improve":
                emit(f"→ self_improve: {args.get('filename')}")
                if self_improve_handler is None:
                    result = "[ERROR] self_improve handler not provided by runtime"
                else:
                    try:
                        result = str(self_improve_handler(args))
                    except Exception as e:
                        result = f"[ERROR] self_improve failed: {e}"
                    did_self_improve = True
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })
                continue

            emit(f"→ {name}")

            if name in modules:
                try:
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        result = str(modules[name].run(**args))
                    captured = buf.getvalue().strip()
                    if captured:
                        for line in captured.splitlines():
                            emit(f"[log] {line}")
                except Exception as e:
                    result = f"[ERROR] {e}"
            else:
                result = f"[ERROR] unknown function: {name}"

            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": result,
            })

        if did_self_improve:
            dyn_tools, modules = _load_functions()
            tools = [SELF_IMPROVE_TOOL] + dyn_tools

    return "[ITERATION LIMIT] reached MAX_ITERATIONS without final response"
