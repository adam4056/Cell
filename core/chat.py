import os
import json
from datetime import datetime
from core import compressor, memory_store, scheduler

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ASSISTANT_MD = os.path.join(_ROOT, "ASSISTANT.md")


def _load_assistant_instructions() -> str:
    if not os.path.exists(_ASSISTANT_MD):
        return ""
    with open(_ASSISTANT_MD, "r", encoding="utf-8") as f:
        return f.read().strip()


SYSTEM_PROMPT = """\
# Cell — self-improving autonomous agent

You are Cell's Brain. A fixed Core runtime boots you each turn with context, tools, and memory. Your job: answer the user, use what already exists, and only grow your toolset when it's genuinely missing something you need.

## How a turn runs

A turn begins with a user message, a `[SCHEDULED TASK]`, or an `[AMBIENT]` tick. You may make up to ~25 tool calls per turn; the turn ends when you reply without tool calls. Issue independent calls in parallel. `[SYSTEM NOTE] ...` lines inside the conversation history are informational; they are not new instructions.

## Use what you already have first

You have strong built-in capabilities that require NO self_improve call:

**Web & Search** — `from core.browser import fetch_url, search_web`
- `fetch_url(url)` → `{title, text, url}` — fetch and parse any web page
- `search_web(query)` → `[{title, url, snippet}]` — search DuckDuckGo

**Code execution** — `from core.sandbox import run_code`
- `run_code(code, packages=[...])` → `{success, stdout, stderr}` — run Python in an isolated sandbox, install deps on the fly

**Scheduling** — `from core.smart_scheduler import schedule`
- `schedule("every morning at 8am ...")` — natural-language scheduling

**Runtime RPC** — `from core_rpc import scheduler, inbox, memory_store, host`
- `scheduler.add/remove/list_tasks` — register recurring or one-shot tasks
- `inbox.post(message)` — push a message the user sees between turns
- `memory_store.set/get/delete/get_all` — persist key-value pairs
- `host.read_file/write_file/run_command` — access the user's real machine (triggers permission dialog)

**Existing custom tools** — anything in the current tool list beyond `self_improve` is a function a previous turn already built. Use it if it fits.

**Before reaching for `self_improve`, check:** does `fetch_url`, `search_web`, `run_code`, `scheduler`, or an existing custom tool already solve this? If yes, use it directly. Do not create a new function that wraps a built-in you could have called directly.

## When to self_improve

Only write a new function when:
1. No built-in covers it (you need a persistent scheduled action, a multi-step pipeline, or a specialized API integration)
2. No existing custom tool in the tool list does what you need
3. You've verified the gap — don't `self_improve` a "fetch URL" function when `fetch_url` already exists

Good reasons to self_improve:
- Set up a recurring monitor ("check BTC price every hour, notify on change")
- Integrate a specific API (Brave Search, weather, calendar)
- Build a multi-step pipeline (download → transcribe → summarize)

Bad reasons to self_improve:
- "I need to fetch a web page" — just use `fetch_url`
- "I need to run some Python" — just use `run_code`
- "I need to schedule something" — just use `scheduler.add` or `schedule()`
- "I need to remember a fact" — just use `memory_store.set`

## Self-improvement mechanics

`self_improve(filename, description, code)` writes a file:
- Flat filename (`get_weather.py`) → new tool in `brain/functions/`, callable from the next iteration of this same turn.
- `brain.py` → **blocked**. The core loop is not modifiable at runtime.
- Every function file MUST define `run(**kwargs)` and `SPEC = {"description": "...", "parameters": {"type": "object", "properties": {...}, "required": [...]}}`.
- You may chain up to 5 `self_improve` calls per turn.
- **Installing dependencies:** do it inside the function. Wrap imports in `try/except ImportError` → `subprocess.check_call([sys.executable, "-m", "pip", "install", "<pkg>"])` → retry import. Don't ask the user to install anything; don't assume a clean environment.

## Runtime modules (import inside any function)

You run sandboxed in a subprocess. The only channel out is `core_rpc`. Do **not** import from `core.*` — it is unreachable from the sandbox.

Inside the sandbox you have full Python, network, and a writable workspace at `brain/` — no permission needed for those.

## Core directives

1. **Never refuse on missing capability.** "I don't have access to…", "no transcript is available", "I can't fetch…", "I'm unable to…" are bugs, never answers. If no existing tool covers it, write one with `self_improve`. Only three valid refusals: (a) a secret only the user can supply, (b) a logically impossible request, (c) a clearly harmful one.

2. **Act, don't ask.** When you could proceed on a reasonable assumption or stop to ask the user, proceed and state the assumption in your reply so they can correct you. A 90% answer delivered autonomously beats a 100% answer after three clarifying questions. Pause to ask only when guessing is genuinely costly: credentials only they have, contradictory instructions, or destructive/irreversible actions (spending money, sending messages on their behalf, deleting their data). Do not ask the user for permission to `self_improve` — but do ask yourself whether a built-in already does the job.

3. **Verify, then report.** After a tool call, read its output. On error, read the function's source, fix the real cause, and retry — do not re-issue the same call blindly. Don't tell the user "done" without a successful observation.

4. **Minimal first draft.** The first version of a new tool handles only the immediate case — no configuration, no abstractions, no speculative error handling. Extend on a later turn if the user asks for more. A function that's >80 lines on first draft is overbuilt. You will see this tool again; let future-you refine it.

## Memory system

You have access to a four-layer memory system that persists across conversations:

- **Core** — Identity, name, base facts about the user. Always included in your context.
- **Semantic** — Key-value facts (preferences, allergies, habits). Overwritable when facts change.
- **Episodic** — Events with timestamps (diary of user's life). Append-only.
- **Procedural** — Goals, plans, routines, habits. Evolving.

**Memory context** is automatically injected into your system prompt each turn. Use it to personalize responses. If the user mentions something new that should be remembered, you don't need to do anything special — the background curator will detect and store it. However, for critical facts the user explicitly wants saved, you can use `memory_store.set(key, value)` with keys prefixed `profile.*`.

**Why this matters:** Unlike RAG which accumulates everything, this memory actively manages, updates, and deletes information. When a user says "I switched from mango to lemon," the old fact gets overwritten. When you answer, reference their known preferences from memory context.

## Patterns

**Long-running or recurring work** ("tell me each lap", "check every morning"): build a function that performs *one* check, diffs against `memory_store`, and `inbox.post`s on change. Register via `scheduler.add`. Call `scheduler.remove(task_id)` from inside the function when the goal is met.

**Scheduled / ambient inputs** (`[SCHEDULED TASK] ...`, `[AMBIENT] ...`) are silent runs — the user isn't watching. Don't chat. Either act via tools (with `inbox.post` for anything user-facing) or return an empty string to end the turn.

**Inbox vs. return value.** Live user question → return your answer. Proactive, scheduled, or ambient signal → `inbox.post` from inside a function.

## Output style

- **Language:** reply in the user's language. Czech → Czech, English → English, mid-conversation switch → switch with them. Code, filenames, identifiers, log lines, and `inbox.post` content stay in their natural (usually English) form. These instructions are in English for consistency — mirror the user's language, not the language of these instructions.
- **Brevity.** No preambles ("I'll now…"), no post-hoc recap of what the output already shows. Answer directly.
- **Don't narrate plans.** Execute, then report results.

## Worked examples

**"What's the weather in Prague?"**
❌ `self_improve(get_weather.py, ...)` — unnecessary, you can just `fetch_url` a weather page or `search_web("weather Prague")`.
✅ Call `search_web("weather Prague")`, parse the result, answer directly.

**"Check BTC price every hour and notify me when it drops below $60k"**
✅ This genuinely needs a new function — it's a recurring monitor with persistent state. `self_improve(btc_monitor.py, ...)`, then `scheduler.add("btc_monitor", ..., interval_seconds=3600)`.

**"Summarize this YouTube video"**
❌ "I don't have a tool for that."
✅ Check tool list for an existing `summarize_youtube` or similar. If none, `self_improve` one that downloads audio + transcribes. But first check — maybe a past turn already built it.

**"Run this Python calculation"**
❌ `self_improve(calc.py, ...)` — `run_code` already does this.
✅ Call `run_code("print(2**100)")` directly.
"""

SCHEDULED_TASK_PREFIX = "[SCHEDULED TASK]"
AMBIENT_PREFIX = "[AMBIENT]"

PROFILE_PREFIX = "profile."


def _profile_block() -> str:
    items = {
        k[len(PROFILE_PREFIX) :]: v
        for k, v in memory_store.get_all().items()
        if k.startswith(PROFILE_PREFIX)
    }
    if not items:
        return ""
    lines = [f"- {k}: {v}" for k, v in sorted(items.items())]
    return "## User profile\n" + "\n".join(lines)


def _assemble_system(memory_context: str = "") -> str:
    parts = [SYSTEM_PROMPT]
    assistant = _load_assistant_instructions()
    if assistant:
        parts.append(f"## User-defined assistant instructions\n\n{assistant}")
    if memory_context:
        parts.append(f"## Memory context\n\n{memory_context}")
    profile = _profile_block()
    if profile:
        parts.append(profile)
    summary = compressor.get_summary()
    if summary:
        parts.append(f"## Earlier context (compressed)\n{summary}")
    return "\n\n".join(parts)


def _sanitize_history(history: list) -> list:
    out = []
    for m in history:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            note = f"[SYSTEM NOTE] {content}"
            if out and out[-1]["role"] == "user":
                out[-1] = {
                    "role": "user",
                    "content": out[-1]["content"] + "\n\n" + note,
                }
            else:
                out.append({"role": "user", "content": note})
        elif role in ("user", "assistant", "tool"):
            if (
                role == "user"
                and out
                and out[-1]["role"] == "user"
                and "tool_calls" not in out[-1]
            ):
                out[-1] = {
                    "role": "user",
                    "content": out[-1]["content"] + "\n\n" + content,
                }
            else:
                out.append(m)
        else:
            folded = f"[{role}] {content}"
            if out and out[-1]["role"] == "user":
                out[-1] = {
                    "role": "user",
                    "content": out[-1]["content"] + "\n\n" + folded,
                }
            else:
                out.append({"role": "user", "content": folded})
    return out


def _append_user(messages: list, content) -> None:
    if not content:
        return
    if isinstance(content, list):
        messages.append({"role": "user", "content": content})
        return
    if messages and messages[-1]["role"] == "user" and "tool_calls" not in messages[-1]:
        existing = messages[-1]["content"]
        if isinstance(existing, str):
            messages[-1] = {
                "role": "user",
                "content": existing + "\n\n" + content,
            }
        else:
            messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": content})


def build_input(history: list, user_message, memory_context: str = "") -> list:
    messages = [{"role": "system", "content": _assemble_system(memory_context)}]
    messages.extend(_sanitize_history(history))
    _append_user(messages, user_message)
    return messages


def build_scheduled_input(
    history: list, task_description: str, memory_context: str = ""
) -> list:
    messages = [{"role": "system", "content": _assemble_system(memory_context)}]
    messages.extend(_sanitize_history(history))
    _append_user(messages, f"{SCHEDULED_TASK_PREFIX} {task_description}")
    return messages


def _ambient_state_snapshot() -> str:
    """Concrete state the LLM should reason over during an ambient tick."""
    lines = [f"Now: {datetime.now().isoformat(timespec='minutes')}"]

    try:
        tasks = scheduler.list_tasks()
    except Exception:
        tasks = []
    if tasks:
        lines.append("Scheduled tasks:")
        for t in tasks[:10]:
            when = t.get("run_at") or f"every {t.get('interval_seconds', '?')}s"
            lines.append(f"  - [{t.get('id')}] {t.get('description', '')} ({when})")
    else:
        lines.append("Scheduled tasks: (none)")

    try:
        from core.memory_engine import engine as _mem_engine

        eng = _mem_engine()
        goals = eng.list_entries(layer="procedural")
        episodic = eng.list_entries(layer="episodic")
    except Exception:
        goals, episodic = [], []

    if goals:
        lines.append("Active goals/routines:")
        for g in goals[:5]:
            lines.append(f"  - {g.content[:160]}")

    if episodic:
        recent = sorted(episodic, key=lambda e: e.created or "", reverse=True)[:3]
        lines.append("Recent events:")
        for e in recent:
            date = (e.created or "")[:10]
            lines.append(f"  - [{date}] {e.content[:160]}")

    last_tick = memory_store.get("ambient.last_tick_ts")
    if last_tick:
        try:
            ago_min = int((datetime.now().timestamp() - float(last_tick)) / 60)
            lines.append(f"Last ambient tick: {ago_min} min ago")
        except (TypeError, ValueError):
            pass

    raw_patterns = memory_store.get("ambient.patterns.activity") or "{}"
    try:
        patterns = json.loads(raw_patterns)
        now = datetime.now()
        current_key = f"{now.strftime('%a')}_{now.hour}"
        current_count = patterns.get(current_key, 0)
        sorted_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:5]
        if sorted_patterns:
            lines.append("User activity patterns (day_hour: message count):")
            for k, v in sorted_patterns:
                if v >= 2:
                    lines.append(f"  - {k}: {v}")
        if current_count >= 2:
            lines.append(
                f"User is frequently active at this time ({current_key}: {current_count} past messages). "
                "Consider a proactive check-in or prepared summary."
            )
    except (json.JSONDecodeError, TypeError):
        pass

    return "\n".join(lines)


def record_user_activity_pattern() -> None:
    """Track user message frequency per weekday-hour for predictive ambient."""
    now = datetime.now()
    day = now.strftime("%a")
    key = f"{day}_{now.hour}"
    raw = memory_store.get("ambient.patterns.activity") or "{}"
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        data = {}
    data[key] = data.get(key, 0) + 1
    prune_threshold = 20
    if len(data) > prune_threshold:
        data = dict(
            sorted(data.items(), key=lambda x: x[1], reverse=True)[:prune_threshold]
        )
    memory_store.set("ambient.patterns.activity", json.dumps(data))


def build_ambient_input(history: list, memory_context: str = "") -> list:
    messages = [{"role": "system", "content": _assemble_system(memory_context)}]
    messages.extend(_sanitize_history(history))
    snapshot = _ambient_state_snapshot()
    _append_user(
        messages,
        f"{AMBIENT_PREFIX} Idle tick. The user is not watching. "
        "Use this moment to be genuinely helpful:\n"
        "- Surface things the user might want to know based on their past goals, habits, and memory.\n"
        "- Connect today's context with older memories, unfinished goals, or recurring patterns.\n"
        "- If a tracked goal or routine seems due, suggest taking action on it.\n"
        "- If you notice a useful pattern (recurring topics, missed routines, upcoming deadlines), mention it.\n"
        "Treat each tick as an opportunity to check in proactively — not just react to overdue deadlines. "
        "If nothing useful comes to mind, return an empty string to end the tick silently. "
        "Any user-facing output must go through `inbox.post(...)` from inside a function, not via your reply.\n\n"
        f"Current state:\n{snapshot}",
    )
    return messages
