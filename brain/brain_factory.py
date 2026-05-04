import os
import sys
import io
import contextlib
import importlib.util
import json

sys.path.insert(0, os.path.dirname(__file__))

import core_rpc

FACTORY_FUNCTIONS_DIR = os.path.join(os.path.dirname(__file__), "factory_functions")
DYNAMIC_FUNCTIONS_DIR = os.path.join(os.path.dirname(__file__), "functions")
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
    """Load tool functions from both factory_functions/ (shipped, in-git) and
    functions/ (dynamic, gitignored, wiped on factory reset). On name
    collision, dynamic wins so the brain can override factory tools."""
    tools = []
    modules = {}
    for fdir in (FACTORY_FUNCTIONS_DIR, DYNAMIC_FUNCTIONS_DIR):
        if not os.path.exists(fdir):
            continue
        for fname in os.listdir(fdir):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            path = os.path.join(fdir, fname)
            mod_spec = importlib.util.spec_from_file_location(fname[:-3], path)
            mod = importlib.util.module_from_spec(mod_spec)
            try:
                mod_spec.loader.exec_module(mod)
            except Exception:
                continue
            if not (hasattr(mod, "SPEC") and hasattr(mod, "run")):
                continue
            name = fname[:-3]
            normalized = _normalize_spec({**mod.SPEC, "name": name})
            entry = {"type": "function", "function": normalized}
            existing = next((i for i, t in enumerate(tools) if t["function"]["name"] == name), None)
            if existing is not None:
                tools[existing] = entry
            else:
                tools.append(entry)
            modules[name] = mod
    return tools, modules


def run(context: list) -> str:
    dyn_tools, modules = _load_functions()
    tools = [SELF_IMPROVE_TOOL] + dyn_tools
    messages = list(context)

    for iteration in range(1, MAX_ITERATIONS + 1):
        message = core_rpc.llm.chat(messages, tools=tools)
        core_rpc.event(f"⏱ llm call #{iteration}")

        if not message.get("tool_calls"):
            return message.get("content", "")

        messages.append(message)

        did_self_improve = False

        for call in message["tool_calls"]:
            name = call["function"]["name"]
            args = json.loads(call["function"]["arguments"])

            if name == "self_improve":
                core_rpc.event(f"→ self_improve: {args.get('filename')}")
                try:
                    result = core_rpc.self_improve(
                        args["filename"], args["code"], args["description"]
                    )
                except Exception as e:
                    result = f"[ERROR] self_improve failed: {e}"
                did_self_improve = True
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })
                continue

            core_rpc.event(f"→ {name}")

            if name in modules:
                try:
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        result = str(modules[name].run(**args))
                    captured = buf.getvalue().strip()
                    if captured:
                        for line in captured.splitlines():
                            core_rpc.event(f"[log] {line}")
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


if __name__ == "__main__":
    init = core_rpc.get_initial_input()
    try:
        response = run(init["messages"])
    except Exception as e:
        import traceback as _tb
        core_rpc.done(f"[SYSTEM ERROR] brain run exception\n{_tb.format_exc()}")
        sys.exit(1)
    core_rpc.done(response)
