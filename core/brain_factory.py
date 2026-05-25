import os
import io
import contextlib
import importlib.util
import json

import core_rpc
from core import skills as skills_module

FACTORY_FUNCTIONS_DIR = os.path.join(os.path.dirname(__file__), "factory_functions")
DYNAMIC_FUNCTIONS_DIR = os.path.join(os.path.dirname(__file__), "functions")
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")
MAX_ITERATIONS = 150

SMART_INTERACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "smart_interaction",
        "description": "Request credentials or configuration from the user via a human-friendly dialog. Write prompts conversationally — the user sees them directly. Use this when you need API keys, tokens, MCP server URLs, or any config the user must supply. You receive only confirmation — NEVER the secret value.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Credential key in UPPER_SNAKE_CASE, e.g. 'OPENWEATHER_API_KEY'."},
                "label": {"type": "string", "description": "Short human name for this credential, e.g. 'OpenWeather API key'."},
                "prompt": {"type": "string", "description": "Friendly explanation the user will READ in the dialog."},
                "secret": {"type": "boolean", "description": "True for secrets (API keys — input shown as ***). Default true."},
            },
            "required": ["key", "label", "prompt"],
        },
    },
}

NOTIFY_TOOL = {
    "type": "function",
    "function": {
        "name": "notify",
        "description": "Send the user an intermediate status update. Use before longer operations (searches, multi-step tasks) so the user knows what you're working on. Example: 'Searching for your Chrome configuration file...' or 'Setting up the weather monitor — this will take a moment.' Keep messages short (under 120 chars).",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Short status message the user sees. Natural language, like you're thinking out loud. Example: 'Let me look that up for you...'",
                },
            },
            "required": ["message"],
        },
    },
}

SKILL_TOOL = {
    "type": "function",
    "function": {
        "name": "skill",
        "description": "Load a skill's full instructions into your context. Skills are procedural knowledge you or the system created. They ship with workflows, patterns, and best practices. Call this when the task matches a skill's described capability.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the skill to load, matching exactly the skill names listed in the system prompt.",
                },
            },
            "required": ["name"],
        },
    },
}

SKILL_CREATE_TOOL = {
    "type": "function",
    "function": {
        "name": "skill_create",
        "description": "Create a reusable skill in skills/<name>/SKILL.md. Use this after completing a complex multi-step task that follows a repeatable pattern. Skills are procedural knowledge: workflows, best practices, domain expertise you want to remember across conversations. Include triggers (keywords that should auto-load this skill).",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short kebab-case name, e.g. 'email-composer'"},
                "description": {"type": "string", "description": "One-line description of what this skill teaches"},
                "triggers": {"type": "array", "items": {"type": "string"}, "description": "Keywords/phrases that auto-load this skill (e.g. ['email', 'send mail', 'compose'])"},
                "body": {"type": "string", "description": "Full markdown instructions — workflow steps, patterns, code examples. This is what gets injected into context when the skill loads."},
            },
            "required": ["name", "description", "triggers", "body"],
        },
    },
}

SKILL_IMPROVE_TOOL = {
    "type": "function",
    "function": {
        "name": "skill_improve",
        "description": "Improve an existing skill's body, triggers, or description. Call this when you discover a better way, when a skill's instructions were incomplete, or after using a skill and finding gaps. Preserves the name, updates everything else.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the skill to improve"},
                "description": {"type": "string", "description": "Updated one-line description"},
                "triggers": {"type": "array", "items": {"type": "string"}, "description": "Updated trigger keywords"},
                "body": {"type": "string", "description": "Updated markdown with improved instructions"},
            },
            "required": ["name", "description", "triggers", "body"],
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


_func_cache: tuple[list, dict] | None = None
_func_mtimes: dict[str, float] = {}


def _load_functions() -> tuple[list, dict]:
    global _func_cache, _func_mtimes
    mtimes = {}
    for fdir in (FACTORY_FUNCTIONS_DIR, DYNAMIC_FUNCTIONS_DIR):
        if os.path.exists(fdir):
            try:
                mtimes[fdir] = os.path.getmtime(fdir)
            except OSError:
                mtimes[fdir] = 0
    if _func_cache is not None and mtimes == _func_mtimes:
        return _func_cache

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
            existing = next(
                (i for i, t in enumerate(tools) if t["function"]["name"] == name), None
            )
            if existing is not None:
                tools[existing] = entry
            else:
                tools.append(entry)
            modules[name] = mod
    _func_cache = (tools, modules)
    _func_mtimes = mtimes
    return tools, modules


def _auto_load_skills(messages: list) -> list[dict]:
    """Find skills matching the last user message and return their content."""
    if not messages:
        return []
    for m in reversed(messages):
        if m.get("role") == "user":
            text = ""
            content = m.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
            return skills_module.find_matching_skills(text)
    return []


def _inject_skills(skills: list[dict], system_msg: dict) -> dict:
    """Append skill bodies to the system message content."""
    if not skills:
        return system_msg
    existing = system_msg.get("content", "")
    blocks = ["\n## Auto-loaded skills (triggered by your message)\n"]
    for s in skills:
        blocks.append(f"### {s['name']}: {s['description']}\n{s['body']}\n")
    return {"role": "system", "content": existing + "\n\n".join(blocks)}


def _load_skill(name: str) -> str | None:
    """Load a skill's SKILL.md content from skills/<name>/SKILL.md."""
    skill_path = os.path.join(SKILLS_DIR, name, "SKILL.md")
    if not os.path.isfile(skill_path):
        return None
    try:
        with open(skill_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _list_skill_names() -> list:
    """List available skill names from the skills/ directory."""
    if not os.path.isdir(SKILLS_DIR):
        return []
    names = []
    for entry in os.listdir(SKILLS_DIR):
        skill_path = os.path.join(SKILLS_DIR, entry)
        if os.path.isdir(skill_path) and os.path.isfile(os.path.join(skill_path, "SKILL.md")):
            names.append(entry)
    return sorted(names)


def run(messages: list) -> str:
    dyn_tools, modules = _load_functions()
    tools = [SMART_INTERACTION_TOOL, NOTIFY_TOOL, SKILL_TOOL, SKILL_CREATE_TOOL, SKILL_IMPROVE_TOOL] + dyn_tools
    msgs = list(messages)

    matching_skills = _auto_load_skills(msgs)
    if matching_skills:
        for i, m in enumerate(msgs):
            if m.get("role") == "system":
                msgs[i] = _inject_skills(matching_skills, m)
                skill_names = ", ".join(s["name"] for s in matching_skills)
                core_rpc.event(f"📋 auto-loaded skills: {skill_names}")
                break

    for iteration in range(1, MAX_ITERATIONS + 1):
        message = core_rpc.llm.chat(msgs, tools=tools)
        core_rpc.event(f"⏱ llm call #{iteration}")

        if not message.get("tool_calls"):
            return message.get("content", "")

        msgs.append(message)

        for call in message["tool_calls"]:
            name = call["function"]["name"]
            args = json.loads(call["function"]["arguments"])

            if name == "smart_interaction":
                core_rpc.event(f"→ smart_interaction: {args.get('key')}")
                try:
                    result = core_rpc.smart_interaction(
                        args["key"],
                        args["label"],
                        args["prompt"],
                        args.get("secret", True),
                    )
                except Exception as e:
                    result = f"[ERROR] smart_interaction failed: {e}"
                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": result,
                    }
                )
                continue

            if name == "notify":
                msg = args.get("message", "")[:200]
                core_rpc.event(f"💬 {msg}")
                result = "[OK]"
                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": result,
                    }
                )
                continue

            if name == "skill":
                skill_name = args.get("name", "")
                content = _load_skill(skill_name)
                if content:
                    core_rpc.event(f"📋 loaded skill: {skill_name}")
                    result = content
                else:
                    available = _list_skill_names()
                    result = f"[ERROR] skill '{skill_name}' not found. Available: {', '.join(available) if available else '(none)'}"
                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": result,
                    }
                )
                continue

            if name == "skill_create":
                skill_name = args.get("name", "")
                core_rpc.event(f"→ skill_create: {skill_name}")
                result = skills_module.create_skill(
                    skill_name,
                    args.get("description", ""),
                    args.get("triggers", []),
                    args.get("body", ""),
                )
                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": result,
                    }
                )
                continue

            if name == "skill_improve":
                skill_name = args.get("name", "")
                core_rpc.event(f"→ skill_improve: {skill_name}")
                result = skills_module.improve_skill(
                    skill_name,
                    args.get("description", ""),
                    args.get("triggers", []),
                    args.get("body", ""),
                )
                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": result,
                    }
                )
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

            msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                }
            )

    return "[ITERATION LIMIT] reached MAX_ITERATIONS without final response"
