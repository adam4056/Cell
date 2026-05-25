# Cell Roadmap

Cell is not a chatbot. It is your **personal AI agent** — the only AI tool you will ever need. One agent that actually does things: manages your life, writes code, controls your computer, browses the web, and remembers everything.

---

## Philosophy

- **One agent to rule them all.** No more switching between ChatGPT, Claude, and a dozen plugins. Cell does it all.
- **It runs on YOUR machine.** Your data, your context, your control. Not a walled garden.
- **Memory is a muscle.** Cell remembers facts in structured layers, not as a chat dump. Personality drifts on a momentum curve — observations move it fast at first, anchor over time. One bad day won't rewrite who you are.
- **Actions > Words.** Cell doesn't just chat — it writes files, sends emails, books flights, controls your home, writes code.
- **Terminal is king.** Fast, keyboard-driven, always-on. GUI is optional candy.
- **You own everything.** Local-first, private, no vendor lock-in.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  CELL AGENT ARCHITECTURE                                    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  1. CORE BRAIN — Self-improving LLM agent            │   │
│  │  • Dynamic tool creation via self_improve           │   │
│  │  • In-process execution with permission gate        │   │
│  │  • Multi-modal: text, images, audio (future)        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  2. MEMORY — Four-layer cognitive memory stack       │   │
│  │  • Core: identity, base facts                       │   │
│  │  • Semantic: key-value facts (overwritable)         │   │
│  │  • Episodic: timeline of events (diary)             │   │
│  │  • Procedural: goals, plans, routines               │   │
│  │  • Big Five personality, cosine-decay EMA momentum  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  3. ACTIONS — The agent's hands and eyes             │   │
│  │  • Browser: browse, fill forms, extract data        │   │
│  │  • System: files, shell commands, scripts           │   │
│  │  • Integrations: Gmail, Calendar, GitHub, etc.      │   │
│  │  • Code: write, test, deploy applications           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  4. COMMS — Where you talk to it                     │   │
│  │  • TUI (primary): fast, always-on terminal UI       │   │
│  │  • Telegram bot (today)                             │   │
│  │  • WhatsApp / Discord / Slack (future)              │   │
│  │  • REST API for external tools                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  5. AUTONOMY — Proactive background execution        │   │
│  │  • Scheduler: recurring & one-shot tasks            │   │
│  │  • Ambient ticks: periodic check-ins                │   │
│  │  • File watchers: react to changes                  │   │
│  │  • Ambient ticks: proactive suggestions             │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Current State (v0.6-dev)

**v0.5.1 — "Cleanup" (structural refactor)**

- [x] Merged Core and Brain into single codebase (in-process brain, no subprocess RPC)
- [x] Removed Web UI (FastAPI + WebSocket) — TUI is the primary interface
- [x] Removed Docker (Dockerfile, docker-compose) — simplified deployment
- [x] Removed complex backup/rollback system; replaced with simple function validation (smoke test on self_improve)
- [x] Tuned system prompts for reuse-first behavior (check built-in + existing tools before self_improve)
- [x] General codebase cleanup (dead code, empty directories, stale artifacts)
- [x] New Web UI added to v1.0 roadmap goal

**v0.5 — shipped**

- [x] Self-improving brain (`self_improve`, dynamic functions)
- [x] Sandboxed execution (subprocess + permission gate)
- [x] Persistent context with compression
- [x] Scheduler engine (recurring & one-shot tasks)
- [x] Telegram bot integration
- [x] File attachments (text, images, PDFs)
- [x] Blessed-based TUI with onboarding wizard
- [x] **Multi-provider** — Anthropic / OpenAI / Gemini / DeepSeek / Ollama
- [x] **Native vision** — multimodal API (Claude Vision / GPT-4V / Gemini)
- [x] **MCP client** — official Python SDK, tools auto-injected
- [x] **PersonaVLM-style four-layer memory** (Core, Semantic, Episodic, Procedural)
- [x] **Embedding retrieval** (multilingual sentence-transformer + keyword fallback)
- [x] **Big Five personality** with cosine-decay EMA momentum
- [x] **Two-stage curator** (per-turn semantic + per-session episodic batch)
- [x] **Auto-healing memory index** (survives manual edits and `/reset`)
- [x] **Proactive ambient agent** — ambient loop with anti-spam guards (cooldown, quiet hours, daily cap)
- [x] **Ambient state snapshot** in prompt (scheduler tasks, goals, recent events, current time)
- [x] **TUI controls** — `/ambient on|off|status|now`
- [x] **Isolated threads** — `chats_store` + `process_chat()`, no memory curation
- [x] **Editable user prompts** — `/edit` command (TUI) reloads last message into input
- [x] **Direct file injection** — TUI `/attach <path>`, backend `_format_file_attachment` handles text, PDFs, images
- [x] **Agent status indicators** — brain events (`→ search_web`, `⏱ llm call #1`) shown as status text next to thinking dots
- [x] **Personality-aware response shaping** — Big Five vector in `memory_personality.summary()` + `_personality_overlay()` in `build_input`; high Neuroticism → softer tone, high Conscientiousness → structured bullets, etc.
- [x] **Document parsing** — DOCX (`python-docx`) and XLSX (`openpyxl`) extraction in `_format_file_attachment`
- [x] **Cost-aware model routing** — heuristic classifier `_classify_complexity()` in `proxy.py`; trivial turns → cheap model; enabled via `auto_route: true` in `config.yaml`
- [x] **Cancel support** — Ctrl+C in TUI cancels the brain subprocess mid-turn

---

## Phase 1: The Agent Core (v0.2 — v0.4)

Goal: Cell becomes a usable AI agent that can work autonomously — remembers you, browses the web, writes code, manages your life.

### v0.2 — "Memory & Identity" ✓ shipped

Full PersonaVLM-style memory subsystem; details in **The Memory Architecture** below.

### v0.3 — "Actions" ✓ shipped

Actions are **agent-driven** — the user writes normal text, the agent decides what tools to use.

- [x] **Code sandbox** — `core/sandbox.py`
  - Agent can execute Python in isolated venv on demand
  - Used for: calculations, data analysis, testing code, scraping
  - User says: *"Calculate factorial of 100"* → agent uses sandbox

- [x] **Browser control** — `core/browser.py`
  - `fetch_url()` — lightweight requests + BeautifulSoup
  - `search_web()` — DuckDuckGo search
  - User says: *"What's the weather in Prague?"* → agent fetches weather site

- [x] **Smart scheduler** — `core/smart_scheduler.py`
  - Agent parses natural language: *"every morning at 8"*, *"tomorrow at 3pm"*, *"in 5 minutes"*
  - Creates scheduled tasks autonomously

- [x] **Permission system v2** — granular access control
  - file_read, file_write, shell_exec, browser_access, code_execution, network_access
  - Policy per type: always_allow / ask / always_deny

### v0.4 — "Proactive Agent" ✓ shipped

Goal: **Cell stops being reactive.** It notices things on its own, speaks up on its own, suggests things on its own.

- [x] **Smart scheduler v2** — natural language:
  - "every morning summarize emails and save to Obsidian"
  - "every hour", "tomorrow at 3pm", "in 5 minutes"
  - `core/smart_scheduler.py` — LLM parsing + heuristic fallback
  - Command: `/schedule <description>`
- [x] **Ambient ticks** — periodic tick that prompts the LLM without user input
  - Loop in `core/core.py` reads interval from settings on every tick (live reload)
  - LLM decides: *say something?* / *do something?* / *stay silent?* (silent return = no-op)
  - Anti-spam guards: cooldown after user msg, quiet hours, daily cap, dedup via memory_store
  - State persists (`ambient.last_tick_ts`, `tick_count`, `tick_date`) — survives restart
- [x] **Ambient intelligence** — *proactive* agent (main goal of v0.4)
  - `build_ambient_input()` injects real-time snapshot: `scheduler.list_tasks()`, top procedural goals, recent episodic events, current time
  - Decision layer driven by prompt (proactive: surfacing goals, memory connections, patterns)
  - Delivery via `inbox.post(...)` → TUI banner / Telegram push
- [x] **TUI controls** — `/ambient on|off|status|now`

→ *Cell works even when you're not at the keyboard.*

---

## Phase 2: Hermes Parity & Beyond (v0.4.1 — v0.8)

**Strategic position:** Hermes Agent (Nous Research) and OpenClaw are today's bar for autonomous AI agents. The goal of phase 2 is to first reach parity with Hermes (v0.5–v0.7) and then surpass it (v0.8) through what Cell does uniquely: four-layer memory, Big Five momentum, Core/Brain isolation with `self_improve`. Before that, a small refactor (v0.4.1) so proactivity is **actually** proactive.

### v0.4.1 — "Proactivity" (unify ambient, loosen the prompt) ✓ shipped

Goal: simplify the proactivity model and make it real.

In code, heartbeat and ambient are **already a single loop today** (`_run_ambient_tick` in `core/core.py:332` — `/heartbeat` just calls `_run_ambient_tick(force=True)`). The split exists only in documentation and UX. On top of that, the prompt in `build_ambient_input` (`core/chat.py:286`) is too conservative ("act only if genuinely due, missed, or broken... do not invent work, do not greet, do not summarize") — that kills the point of proactivity.

- [x] **One name: ambient** — heartbeat disappears from docs and from TUI
  - TUI: `/ambient on|off|status` stays; `/ambient now` replaces `/heartbeat`
  - README + ROADMAP: one concept, one section
- [x] **Loosen the prompt** — `build_ambient_input` in `core/chat.py:286`
  - Removed "Do not invent work, do not greet, do not summarize"
  - Added positive instruction: actively surface user-relevant info based on memory and patterns, don't just wait for a deadline
  - Anti-spam guards (cooldown, quiet hours, daily cap) stay — the loosening is in the *nature* of the action, not the frequency
- [x] **Proactive triggers** — what ambient is allowed to initiate on its own
  - Reminder of a goal from procedural memory ("you said you wanted a weekly review — shall we do it now?")
  - Connection between today's context and older memory ("you mentioned X last month, today it might relate to Y")
  - Suggest next action after completing a big task
  - Surface relevant content from `[AMBIENT]` snapshot, not just react to expired tasks
- [x] **Predictive ambient** *(moved from v0.8)*
  - Time patterns: "user handles emails every Monday at 9:00" → prepare a summary in advance
  - Anomalies: "user hasn't checked morning email for 3 days" → soft check-in
  - Implementation: frequency tracker in `memory_store` (`ambient.patterns.*`) + detection in `_ambient_state_snapshot`

→ *Cell speaks up when it has something to say — not just when something "slipped".*

---

### Where Cell stands vs Hermes (audit, 2026-05)

| Area | Hermes | Cell today |
|---|---|---|
| Multi-model | yes (model-agnostic) | DeepSeek / OpenAI / Anthropic / Gemini / Ollama |
| Vision | native | native multimodal API |
| MCP client | yes | `core/mcp_client.py` |
| Browser automation | full (multi-backend) | only `fetch_url` (static HTML) |
| Voice I/O | STT + TTS + Discord voice | missing |
| Subagents | isolated, parallel | missing |
| Batch processing | yes | missing |
| Image generation | yes | missing |
| Skill marketplace | agentskills.io standard | `self_improve` locally, no sharing |
| Multi-channel | TG / Discord / Slack / WA / Signal / Email | TUI / TG / Web |

### v0.5 — "Brain Stem" (multi-model + vision + MCP) ✓ shipped

Goal: break the DeepSeek dependency and open up to the MCP ecosystem.

- [x] **Multi-provider proxy** — refactor `core/proxy.py` to adapter pattern
  - Anthropic (Claude 4.x), OpenAI, Gemini, DeepSeek, llama.cpp local
  - Per-turn model choice (`/model claude-opus-4-7`)
  - Different models for brain vs. curator (cheap for curation, smart for decisions)
  - BYOK via `config.yaml`, `~/.cell-2/keys.json`
- [x] **Native vision** — `image/*` MIME goes straight into the multimodal API
  - Claude Vision / GPT-4V / Gemini, no base64 fallback
  - Replaces `_format_file_attachment` image branch in `core/core.py`
- [x] **MCP client** — `core/mcp_client.py`
  - Support for the official Python `mcp` SDK
  - Tools from MCP servers automatically appear in the brain tool list
  - Per-server config in `config.yaml` (gh, gmail, fs, etc.)
  - Permission gate respects per-server scope

→ *Cell is no longer DeepSeek-only and opens up to the MCP ecosystem.*

### v0.6 — "Restart" (TUI rebuild + smart interaction)

Goal: rebuild the TUI from scratch and introduce a secure credential flow that keeps secrets out of LLM context.

- [ ] **Rebuild TUI from scratch** — fresh implementation with proper architecture
- [ ] **Smart interaction** — a function-calling tool that lets the agent request credentials/config from the user interactively
  - Agent calls `smart_interaction` via function calling (e.g. when it detects MCP would help)
  - TUI presents a dialog for the user to enter the required data (API keys, MCP server URLs, etc.)
  - System stores values in `credentials.json` as constants, **not** the agent
  - LLM only sees variable names (e.g. `OPEN_METEO_API_KEY`), never the actual secrets
  - Increases security (LLM never touches secrets) and efficiency (no long keys in context)
  - Generated `self_improve` functions can reference these credentials by name too
  - **Rule:** Everything except core system config (main model API key) moves to `credentials.json`; core config stays in `config.yaml`

---

## The Memory Architecture

Cell's memory is not a dump. It is a **living, layered mind**.

### Space & Chapters

The **Space** is your single, infinite chat — it never resets, never branches, never rolls over. You always pick up where you left off.

Inside that infinite Space, Cell silently breaks the timeline into **chapters**. A chapter is just a stretch of turns separated from the next by a long pause (default: 60 minutes idle). Chapters are *internal* — you don't see them as anything other than a brief `Session #N closed — captured X memory items` notice when one ends.

Why chapters? Two updates run on different rhythms:

- **Per turn** (after every message you send): Cell extracts atomic semantic facts and nudges your personality vector.
- **Per chapter** (when one closes): Cell summarizes the whole stretch into 1–5 atomic episodic events, plus any identity-level (core) or goal-level (procedural) updates.

Threads (v1.6) will be *named* chapters you can spawn explicitly.

### Four Layers

| Layer | What | Analogy | CRUD |
|-------|------|---------|------|
| **Core** | Identity, name, base facts | OS Settings | Update |
| **Semantic** | Key-value facts | Contacts | CRUD |
| **Episodic** | Events with timestamps | Message history | Create, Read |
| **Procedural** | Goals, routines, plans | Calendar + Habits | CRUD |

### Why RAG Alone Sucks

Classic RAG cannot delete or update. If you say "I drink mango" and later "I drink lemon", RAG stores BOTH. When you ask "what should I drink?", it suggests mango because it was mentioned more often. Cell overwrites facts directly in the Semantic layer.

### Personality Momentum (λ)

Personality is a Big Five vector (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism), each on 1–5. After every user turn the curator infers a per-turn observation `p'_m` and the stored profile `p_m` updates via exponential moving average:

```
p_m = λ_m · p_{m-1} + (1 − λ_m) · p'_m
λ_m = 0.7 − 0.2 · cos(min(m, 50) / 50 · π)
```

- **Turn 1**: λ ≈ 0.5 — fresh slate, observations move the profile fast.
- **Turn 50+**: λ ≈ 0.9 — anchored to history, one bad Tuesday won't rewrite the user.
- All-neutral observations (every trait = 3) are discarded, so silent turns don't drag the profile back to centre.

Cell tracks **climate**, not just **weather**.

### Three-Phase Update

**Phase 1 — Response (~1s, blocking).** Embedding-based retrieval over all four layers builds the memory context that ships with the next reply.

**Phase 2 — Per-turn (background).** After each reply, the curator LLM extracts atomic semantic facts and infers a Big Five observation; personality EMA ticks once.

**Phase 3 — Per-chapter (background).** When the chapter closes (60 min idle or `/memory end-session`), the curator LLM gets the full chapter dialogue and emits 1–5 atomic episodic events plus any core / procedural CRUD operations.

---

## Contributing

Pick a milestone, open an issue, or just start hacking. The brain is self-improving — your code might teach the agent to write even better code.
