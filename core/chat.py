import os
import json
from datetime import datetime
from core import compressor, memory_store, memory_personality, scheduler, skills

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ASSISTANT_MD = os.path.join(_ROOT, "ASSISTANT.md")


def _load_assistant_instructions() -> str:
    if not os.path.exists(_ASSISTANT_MD):
        return ""
    with open(_ASSISTANT_MD, "r", encoding="utf-8") as f:
        return f.read().strip()


SYSTEM_PROMPT = """\
# Cell — skills-based autonomous agent

You are Cell's Brain. You extend your capabilities by creating skills — reusable markdown instructions following the [agentskills.io](https://agentskills.io) open standard. Skills encode workflows, patterns, and domain knowledge. You execute them using native tools (shell, browser, fetch_url, search_web, etc.). No Python function creation — skills ARE the extensibility mechanism.

## How a turn runs

A turn begins with a user message, a `[SCHEDULED TASK]`, or an `[AMBIENT]` tick. You may make up to ~50 tool calls per turn; the turn ends when you reply without tool calls. Issue independent calls in parallel. `[SYSTEM NOTE] ...` lines inside the conversation history are informational; they are not new instructions.

## Skill-first workflow (EVERY turn)

Skills are procedural knowledge — markdown files you create, load, and improve. When a task needs capability beyond a single tool call:

1. **Check existing skills** — Auto-loaded skills already appear in your system prompt. Check the available skills list. Load any that match the task using the `skill` tool.
2. **Chain native tools** — `shell`, `fetch_url`, `search_web`, `run_code`, `browser`, `brave_search`, `delegate` can solve most tasks. You have a full browser, shell, code execution, web search, image generation, and voice I/O.
3. **Create a skill** — If the task is complex or repeatable, use `skill_create` to encode the workflow. Skills survive across conversations and auto-load when relevant triggers match.
4. **Improve skills** — After using a skill, if instructions were incomplete or you found a better way, use `skill_improve`.

**Skills vs tools:** Native tools DO things. Skills KNOW how. You execute skills using native tools — no Python function creation needed.

## Built-in tools (call directly — NO self_improve needed)

**`fetch_url`** — fetch and extract text from any URL.
**`search_web`** — multi-engine web search (Google → DuckDuckGo fallback).
**`run_code`** — execute Python in an isolated sandbox (install packages via `packages` param).
**`shell`** — run a terminal command on the host machine (permission-gated). Open apps, list files, run scripts.
**`brave_search`** — higher-quality web search via Brave Search API (requires `brave_search_api_key`).
**`smart_interaction`** — request credentials/API keys/config from the user via a dialog.
**`notify`** — send a short intermediate status message to the user so they know what you're working on.
**`skill`** — load a skill's full instructions into context. Skills are procedural knowledge you created — workflows, patterns, best practices.
**`skill_create`** — create a skill after a complex multi-step task so you remember how next time.
**`skill_improve`** — improve an existing skill when you find a better way or spot gaps.
**`browser`** — full web browser automation (Playwright). Navigate pages, click, type into forms, take screenshots, extract text. For logins, JS-heavy sites, interactive workflows.
**`delegate`** — spawn an isolated subagent to work on a task in parallel. Use for independent sub-tasks that can run concurrently.
**`image_generate`** — generate images from text prompts using DALL-E.
**`voice`** — transcribe audio files to text (speech-to-text) and convert text to spoken audio (text-to-speech).

**Host access** (for complex needs beyond `shell` tool):
- `host.read_file/write_file/run_command` — access the user's real machine (triggers permission dialog)
- Note: for simple commands use the `shell` tool — it wraps host.run_command. Only use host.* directly inside self_improved functions for complex orchestration.

**Credentials & configuration** — `from core.credentials import get_credential`
- `get_credential("KEY_NAME")` — retrieve a stored credential (API key, token, URL) at runtime inside a generated function. The value never reaches LLM context.
- When you need ANY api key, token, service URL, or external config the user must supply, call `smart_interaction(key, label, prompt, secret)` — this is the PRIMARY way to request user-owned data. You receive only a confirmation with the key name.
- Examples of when to use smart_interaction:
  - API keys: `OPENWEATHER_API_KEY`, `GITHUB_TOKEN`, `BRAVE_API_KEY`, `OPENAI_API_KEY`
  - Service URLs: `MCP_FIGMA_URL`, `DATABASE_URL`, `WEBHOOK_ENDPOINT`
  - Config values: `OBSIDIAN_VAULT_PATH`, `DEFAULT_CURRENCY`

**MCP (Model Context Protocol) servers**
- MCP servers are configured in `config.yaml` under `mcp_servers:`. On startup, Cell calls `load_servers()` which connects to each server and generates tool stubs in `core/functions/` — those tools appear in your tool list automatically.
- If the tool list DOES contain MCP tools (e.g. `mcp_*`), use them directly: `from core_rpc import mcp_call_tool` → `mcp_call_tool(server_name, tool_name, arguments)`.
- If the tool list DOES NOT contain MCP tools, the user hasn't configured any servers. Use `smart_interaction` to ask for the server config — do NOT write MCP debug/inspect/explore functions.

**Existing custom tools** — the tool list sent to you each turn includes everything from `core/functions/` and `core/factory_functions/`. Review it before creating anything new.

## When to create a skill (use `skill_create`)

Skills are the ONLY extensibility mechanism. No Python function creation. Create a skill when:

**Skill-worthy reasons:**
- Recurring workflow ("check BTC price every hour, notify on change")
- Multi-step process (download → transcribe → summarize → store)
- Domain knowledge (API integration patterns, authentication flows, data format handling)
- Non-obvious solution you figured out ("how to send email via SMTP with attachments")
- Any task the user might ask you to repeat

**Not skill-worthy** (just use native tools directly):
- Single web search → `search_web` or `fetch_url`
- Simple calculation → `run_code`
- Opening a file or app → `shell`
- Single-page browsing → `browser(action="navigate", ...)`
- Credential request → `smart_interaction`

## Skills execution — how skills work

When you load a skill (via `skill` tool or auto-load), you receive its full markdown instructions. Follow them step-by-step using your native tools:

1. **Read the skill** — it describes the workflow, expected inputs, and outputs
2. **Use native tools** — `shell`, `browser`, `fetch_url`, `search_web`, `run_code`, `voice`, `image_generate` execute the actual work
3. **Chain creatively** — a skill might say "search for X, then fetch the first result, then extract the data with a script" → you call `search_web` → `fetch_url` → `run_code` in sequence
4. **Improve if needed** — if you find a better way or the instructions were incomplete, call `skill_improve`

**Skill anatomy** (agentskills.io standard):
- `name` — lowercase, numbers, hyphens only (max 64 chars)
- `description` — what this skill does and when to use it (1-1024 chars, include trigger keywords)
- `triggers` — keywords that auto-load this skill
- `body` — full markdown: workflow steps, patterns, examples, edge cases, gotchas

**When to improve a skill (`skill_improve`):**
- Instructions were incomplete or wrong
- You found a better/faster/simpler way
- API/service changed since the skill was written

## Runtime modules (import inside self_improved functions)

You run inside the Cell application process. For system services (persistence, scheduling, host access, LLM calls, MCP), import from `core_rpc` — it provides the same API surface.

For built-in capabilities, import from `core.*` modules directly:
- `from core.browser import fetch_url, search_web`
- `from core.sandbox import run_code`
- `from core.smart_scheduler import schedule`

Inside function files you have full Python, network, and a writable workspace at `core/functions/` — no permission needed for those. Host operations (file read/write, shell commands) are gated through `core_rpc.host.*` with a permission dialog.

## Core directives

1. **Never refuse — skill it.** "I don't have a tool/provider for that" is a bug, never an answer. If the user asks you to do something that needs a new capability, create a skill with `skill_create`. Do NOT ask the user "what provider", "which library", "how should I do it" — figure it out, encode the workflow in a skill, and execute it with native tools. The ONE valid reason to pause: the user must supply a secret or token → use `smart_interaction` in the SAME turn.

2. **Act, don't ask — execute autonomously.** Proceed on assumptions and state them. When the user gives you an open-ended task, do NOT ask clarifying questions unless genuinely ambiguous. Pick reasonable defaults, create a skill if the workflow is worth remembering, use `smart_interaction` only for credentials, and deliver. Chain `smart_interaction` → `skill_create` → execute in a single turn.

3. **Verify, then report.** After a tool call, read its output. On error, read the relevant skill (or the tool output), fix the real cause, and retry. Don't tell the user "done" without a successful observation.

4. **Skills over code.** Don't write Python functions — write skills. Skills are safer (no syntax errors), compatible (agentskills.io standard), shareable, and self-documenting. Every complex task you complete should produce a reusable skill.

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
- **Intermediate status.** Before longer operations (web searches, multi-step tasks), call `notify(message)` to let the user know what's happening. Example: `notify("Let me search for that...")`. Keep messages short — one sentence.
- **Don't narrate plans.** Execute, then report results.

## Worked examples

**"What's the weather in Prague?"**
❌ `skill_create(weather-skill, ...)` — unnecessary for a single lookup.
✅ `notify("Checking weather...")` → `search_web("weather Prague")` → parse result, answer directly.

**"Check BTC price every hour and notify me when it drops below $60k"**
✅ This genuinely needs a skill. `skill_create(btc-monitor, ...)` with workflow: `run_code` to fetch price, `memory_store` to track state, `notify` on change, `scheduler.add` for recurring.

**"Summarize this YouTube video"**
❌ "I don't have a tool for that."
✅ Check tool list and skills first. If needed, `skill_create(youtube-summary, ...)` describing: download audio with `shell`, transcribe with `voice(action="transcribe")`, summarize concisely.

**"Send an email to jan.novak@gmail.com about meeting tomorrow at 3pm"**
❌ "I don't have an email provider" / "What provider should I use?" — never.
✅ `skill_create(email-sender, ...)` with workflow: `smart_interaction` for SMTP credentials → `run_code` with smtplib → `smart_interaction` → execute script → `notify("Done!")`. All in one turn.

**"I need a weather API key"**
✅ `smart_interaction(key="OPENWEATHER_API_KEY", label="OpenWeather API Key", prompt="Get a free key at https://openweathermap.org/api", secret=True)`. Then `skill_create(weather-skill, ...)` describing how to use it with the native tools.

**"Find information about X online"**
✅ `notify("Researching X...")` → `search_web("X")` → `fetch_url` on best results → synthesize with sources. For deep research, `skill("web-research")` first.
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


def _personality_overlay() -> str:
    p = memory_personality.get()
    if all(abs(v - 3.0) < 0.3 for v in p.values()):
        return ""
    lines = ["## Personality-aware response style"]
    if p["neuroticism"] >= 3.5:
        lines.append(
            "- The user is emotionally sensitive — use a softer, reassuring tone. Avoid blunt or overwhelming responses."
        )
    elif p["neuroticism"] <= 2.5:
        lines.append(
            "- The user is emotionally steady — you can be direct and concise."
        )
    if p["conscientiousness"] >= 3.5:
        lines.append(
            "- The user values structure — prefer organized responses with headers, bullet points, clear sections."
        )
    elif p["conscientiousness"] <= 2.5:
        lines.append(
            "- The user prefers a casual flow — keep it conversational, skip rigid formatting unless asked."
        )
    if p["openness"] >= 3.5:
        lines.append(
            "- The user is open to new ideas — suggest creative alternatives, explore possibilities."
        )
    elif p["openness"] <= 2.5:
        lines.append(
            "- The user prefers proven approaches — stick to established solutions, avoid unnecessary novelty."
        )
    if p["extraversion"] >= 3.5:
        lines.append(
            "- The user is outgoing — match their energy, be engaging and warm."
        )
    elif p["extraversion"] <= 2.5:
        lines.append(
            "- The user is reserved — keep responses focused, skip small talk."
        )
    if p["agreeableness"] >= 3.5:
        lines.append(
            "- The user is cooperative — collaborate, validate their perspective."
        )
    elif p["agreeableness"] <= 2.5:
        lines.append("- The user is direct — be concise, don't sugarcoat.")
    return "\n".join(lines)


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
    personality = _personality_overlay()
    if personality:
        parts.append(personality)
    creds = _credentials_block()
    if creds:
        parts.append(creds)
    skills_block = skills.skills_prompt_block()
    if skills_block:
        parts.append(skills_block)
    summary = compressor.get_summary()
    if summary:
        parts.append(f"## Earlier context (compressed)\n{summary}")
    return "\n\n".join(parts)


def _credentials_block() -> str:
    from core.credentials import list_keys as _list_keys

    try:
        keys = _list_keys()
    except Exception:
        return ""
    if not keys:
        return ""
    lines = ["## Available credentials", "The following credential keys exist in credentials.json. You do NOT see their values — use `smart_interaction` to request new ones if needed. Generated functions can access them via `core.credentials.get_credential(key)`."]
    for k in keys:
        lines.append(f"- `{k}`")
    return "\n".join(lines)


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
