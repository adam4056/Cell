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
│  │  • Sandboxed execution with permission gate         │   │
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

## Current State (v0.5)

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
- [x] **Web UI** — FastAPI + WebSocket, cream pill design, Space/Chats toggle
- [x] **Isolated threads** — `chats_store` + `process_chat()`, no memory curation

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
- [ ] **File watcher triggers** *(nice-to-have, low priority)* — react to file changes

→ *Cell works even when you're not at the keyboard.*

---

## Phase 2: Hermes Parity & Beyond (v0.4.1 — v0.8)

**Strategic position:** Hermes Agent (Nous Research) and OpenClaw are today's bar for autonomous AI agents. The goal of phase 2 is to first reach parity with Hermes (v0.5–v0.7) and then surpass it (v0.8) through what Cell does uniquely: four-layer memory, Big Five momentum, Core/Brain isolation with `self_improve`. Before that, a small refactor (v0.4.1) so proactivity is **actually** proactive.

### v0.4.1 — "Proactivity" (unify ambient, loosen the prompt) ✓ shipped

Goal: simplify the proactivity model and make it real.

In code, heartbeat and ambient are **already a single loop today** (`_run_ambient_tick` in `core/core.py:332` — `/heartbeat` just calls `_run_ambient_tick(force=True)`). The split exists only in documentation and UX. On top of that, the prompt in `build_ambient_input` (`core/chat.py:286`) is too conservative ("act only if genuinely due, missed, or broken... do not invent work, do not greet, do not summarize") — that kills the point of proactivity.

- [x] **One name: ambient** — heartbeat disappears from docs and from TUI/Web
  - TUI: `/ambient on|off|status` stays; `/ambient now` replaces `/heartbeat`
  - Web UI: one control panel, unified naming
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

### v0.6 — "Hands, Eyes, Voice" (browser, voice, image gen)

Goal: catch up to Hermes on "action" features.

- [ ] **Full browser** — `core/browser_full.py` via Playwright
  - JS rendering, login flows, form filling, screenshot
  - `fetch_url` stays as the lightweight default; new `browse(url, actions=[...])` for full interaction
  - Headless / headed switch for debugging
- [ ] **Voice I/O** *(consider deferring past v0.8 — low differentiation, only catch-up vs Hermes)*
  - **STT:** Whisper local (CPU+GPU) → text in TUI / Web / Telegram
  - **TTS:** Piper / Coqui → voice replies
  - Later: Discord voice channel (live conversation)
- [ ] **Image generation** — `generate_image(prompt)` via DALL·E / Replicate / local Stable Diffusion
- [ ] **Document parsing** — DOCX, XLSX, native PDF (`pypdf`, `python-docx`, `openpyxl`)
- [ ] **Audio messages** — Cell sends a voice memo on Telegram / WhatsApp
- [ ] **Cost-aware model routing** — per-turn classifier (trivial / medium / complex) → cheapest capable model
  - Trivial (greeting, short answer) → Haiku / DeepSeek-chat / local
  - Medium (regular turn with memory retrieval) → Sonnet / DeepSeek-reasoner
  - Complex (multi-tool, planning, `self_improve`) → Opus / GPT-5
  - Classifier: heuristics (length, tool count, keywords) + lightweight LLM scorer; cache by prompt hash
  - Curator already uses a cheap model — generalize the pattern across the whole chat; expected savings 5–10× without quality loss
- [ ] **Personality-aware response shaping** *(moved from v0.8, low effort high impact)*
  - User's Big Five vector drives reply style: high Neuroticism → softer tone; high Conscientiousness → structure, bullets
  - Per-user prompt overlay in `build_input` — no big refactor, just a layer on top of the system prompt
  - Strengthens the EMA momentum feedback loop: better shaping → more accurate user reactions → more accurate persona

→ *Cell has all the senses and hands Hermes has — and chooses "how much brain" to spend.*

### v0.7 — "Subagents & Reach" (parallelization, channels, marketplace)

Goal: parallel compute + reachable from anywhere + skill sharing.

- [ ] **Subagents** — `runner.spawn_subagent(task, context)`
  - Wrapper over `run_brain_subprocess` with isolated context
  - Returns the result without contaminating the main turn
  - Use: parallel research, batch processing, "delegate to specialist"
- [ ] **Batch processing** — `cell2 batch <prompts.jsonl>` CLI
  - Hundreds / thousands of prompts in parallel, JSON output
  - Per-item subagent
- [ ] **Discord bot** — analogue of `core/telegram_bot.py`
- [ ] **Slack bot** — workspace integration
- [ ] **WhatsApp** — Business API (later Signal, iMessage)
- [ ] **Email channel** — IMAP poll + SMTP send
- [ ] **REST API stabilization** — finalize `/api/*`, OpenAPI spec
- [ ] **Webhook receivers** — GitHub, Sentry, Linear → ambient triggers
- [ ] **Skill registry**
  - `brain/functions/*.py` → exportable package (manifest + deps + spec + hash + author)
  - Compatible with agentskills.io (if the spec allows)
  - `cell2 skills export <name>` / `cell2 skills install <url>`
  - **Trust tiers** — an imported skill is not added directly to `brain/functions/`
    - Tier 0 (untrusted): runs in an isolated subprocess, network=deny, fs=read-only sandbox dir
    - Tier 1 (probationary): promoted after N successful runs without errors / permission breaches
    - Tier 2 (trusted): manually approved by user, full permissions per manifest scope
    - Provenance: hash + source URL + install date in `~/.cell-2/skills.json`

→ *Cell == Hermes feature parity.*

### v0.8 — "Beyond Hermes" (differentiation)

Goal: leverage Cell's unique strengths and surpass Hermes on four axes: memory, self-improvement safety, prediction, local AI.

- [ ] **Self-improving brain v2** — `self_improve` as a production pipeline, not a toy
  - **LLM-as-reviewer** — independent instance reads every proposed change (security, bugs, regressions)
  - **Test-driven** — generated function **must** ship with a test; the test runs in the sandbox before merge; fail → old code stays
  - **Adversarial subagent** — second LLM in a "red team" role tries to break/exploit the change (edge cases, injection, infinite loop)
  - **Regression memory** — history of everything `self_improve` ever broke; injected into the reviewer's prompt ("you broke this last time — don't try again")
  - **Lineage tracking** — every generated tool has a parent pointer; periodic pruning of obsolete versions
- [ ] **Sleep cycle / dream pass** — nightly memory consolidation *(killer feature — no cloud agent does this)*
  - During quiet hours the agent walks through closed chapters and runs:
    - **Contradiction sweep** — finds contradictions in Semantic ("user drinks coffee" vs. "user doesn't drink coffee") and resolves via timestamp + frequency
    - **Redundancy merge** — merges duplicate / similar facts (cosine similarity over embeddings)
    - **Meta-summary** — from N chapters generates a higher-level abstraction ("over the last 14 days the user worked on refactor X")
    - **Goal review** — walks Procedural, marks stagnating / completed goals, suggests updates
  - Implementation: extend `core/memory_curator.py` with a `consolidate()` pass; runs via the ambient loop in quiet hours, batched over chapters since last consolidation
  - Dream output is its own layer (`memory/dreams/`), user views it via `/memory dreams`
- [ ] **OS-level ambient signals** *(moved from v1.5 — without this, "ambient" is just a timer)*
  - **Clipboard watcher** — when the user copy-pastes large text, ambient may react ("looks like a legal doc, want me to prepare a summary?")
  - **Active window observer** — Cell knows what the user is looking at (PDF, IDE, browser tab) → context without asking
  - **Recent files** — what the user opened / modified in the last hour → ambient signal for a proactive trigger
  - Implementation: lightweight background daemon (Windows: `pywin32`; macOS: AppleScript / `Quartz`; Linux: `xdotool`/`wmctrl`)
  - Privacy gate: per-app whitelist, clipboard never persisted without explicit consent
- [ ] **Persona forking** — "coding assistant", "researcher", "therapist" personas
  - Shared Core memory (who the user is) + per-persona Procedural & Episodic
  - `/persona researcher`
- [ ] **Local fine-tuning** — user data → personal LoRA
  - Fine-tune a local Llama / Qwen on user-specific patterns (data never leaves the machine)
  - Cell learns "how this specific person thinks" — Hermes doesn't do this
- [ ] **Memory provenance & undo** — every `memory_engine.add()` has a source pointer
  - *"Why does Cell think I'm allergic to strawberries?"* → shows the sentence from a conversation 3 weeks ago
  - `/memory revert <id>` — undo a specific memory without touching neighbors
- [ ] **Encrypted-at-rest by default** — `memory/`, `context.json`, `chats/` encrypted
  - Master passphrase or OS keychain
  - Zero-knowledge: without the key, even Cell itself cannot read old state
- [ ] **Multi-device E2EE sync** — own relay or Syncthing wrapper
  - Phone ↔ laptop ↔ server: same persona, same memory
  - Conflict resolution: "newest semantic, append-merge episodic"

→ *Cell is no longer a Hermes clone — it has deeper memory, a sleep cycle, safe self-improvement with tests and a red team, ambient OS signals, and local fine-tuning.*

---

## Phase 3: Production (v1.0)

Goal: a product ready for wide use.

### v1.0 — "The Workstation"
- [ ] **Docker support** — full Cell as a Docker container
  - `docker run -it cell2` — instant start
  - Persistent volume for `memory/`, `context.json`, `chats/`, config
  - Ideal for 24/7 server deployment; docker-compose with Redis/Postgres
- [ ] **Optional GUI** — lightweight native GUI; TUI stays primary
- [ ] **Installer & auto-update** — Windows MSI / macOS DMG / Linux AppImage
- [ ] **Companion app (macOS)** — menubar access, native notifications
- [ ] **Local LLM by default** — llama.cpp or similar; cloud as fallback
- [ ] **Agent marketplace** — sharing and discovery of skill packages (extension of v0.7 registry)

→ *Now it's a product for normal people.*

---

## Phase 4: Advanced (v1.5+)

### v1.5 — "Ambient Intelligence v2"
- [ ] **Native system notifications** — Cell pushes via OS notification center (Windows toast, macOS NC, Linux libnotify)
- [ ] **Advanced analytics** — analysis of user behavior, productivity, habits
- [ ] **Ambient action proposals** — not just "say something", but "do something" with a confirm dialog (e.g., after copy-paste auto-prepare a response template)

### v1.6 — "Team Mode"
- [x] **Thread system** *(shipped in v0.5 web UI)*
- [ ] **Team Mode** — multiple users, shared session
- [ ] **Shared sessions** — two people + agent in one conversation

→ *Now it does team collaboration too.*

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
