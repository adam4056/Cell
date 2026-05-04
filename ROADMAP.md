# Cell-2 Roadmap

Cell-2 is not a chatbot. It is your **personal AI agent** — the only AI tool you will ever need. One agent that actually does things: manages your life, writes code, controls your computer, browses the web, and remembers everything.

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
│  CELL-2 AGENT ARCHITECTURE                                  │
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
│  │  • Heartbeats: periodic check-ins                   │   │
│  │  • File watchers: react to changes                  │   │
│  │  • Ambient ticks: proactive suggestions             │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Current State (v0.2)

- [x] Self-improving brain (`self_improve`, dynamic functions)
- [x] Sandboxed execution (subprocess + permission gate)
- [x] Persistent context with compression
- [x] Scheduler engine (recurring & one-shot tasks)
- [x] Telegram bot integration
- [x] File attachments (text, images, PDFs)
- [x] Textual TUI with onboarding wizard
- [x] DeepSeek / OpenAI-compatible API support
- [x] **PersonaVLM-style four-layer memory** (Core, Semantic, Episodic, Procedural)
- [x] **Embedding retrieval** (multilingual sentence-transformer + keyword fallback)
- [x] **Big Five personality** with cosine-decay EMA momentum
- [x] **Two-stage curator** (per-turn semantic + per-session episodic batch)
- [x] **Auto-healing memory index** (survives manual edits and `/reset`)

---

## Phase 1: The Agent Core (v0.2 — v0.4)

Cíl: Cell se stane použitelným AI agentem co umí pracovat autonomně — pamatuje si vás, browsuje web, píše kód, spravuje váš život.

### v0.2 — "Memory & Identity" ✓ shipped

Full PersonaVLM-style memory subsystem; details in **The Memory Architecture** below.

### v0.3 — "Actions" ✓ shipped

Actions are **agent-driven** — the user writes normal text, the agent decides what tools to use.

- [x] **Code sandbox** — `core/sandbox.py`
  - Agent can execute Python in isolated venv on demand
  - Used for: calculations, data analysis, testing code, scraping
  - User says: *"Spočítej mi faktoriál 100"* → agent uses sandbox

- [x] **Browser control** — `core/browser.py`
  - `fetch_url()` — lightweight requests + BeautifulSoup
  - `search_web()` — DuckDuckGo search
  - User says: *"Jaké je počasí v Praze?"* → agent fetches weather site

- [x] **Smart scheduler** — `core/smart_scheduler.py`
  - Agent parses natural language: *"každé ráno v 8"*, *"zítra v 15:00"*, *"za 5 minut"*
  - Creates scheduled tasks autonomously

- [x] **Permission system v2** — granular access control
  - file_read, file_write, shell_exec, browser_access, code_execution, network_access
  - Policy per type: always_allow / ask / always_deny

### v0.4 — "Proactive Agent" (partial)
- [x] **Smart scheduler v2** — přirozený jazyk:
  - "každé ráno shrň maily a ulož do Obsidianu"
  - "každá hodina", "zítra v 15:00", "za 5 minut"
  - `core/smart_scheduler.py` — LLM parsing + heuristic fallback
  - Příkaz: `/schedule <description>`
- [ ] **Heartbeats** — agent se sám hlásí, ptá se co potřebuješ
- [ ] **File watcher triggers** — reakce na změny souborů
- [ ] **Ambient intelligence** — proaktivní návrhy (kalendář, počasí, deadline)
- [ ] **Skill marketplace** — komunitní pluginy (hotové integrace)

→ *Teď máš agenta co umí pracovat za tebe 24/7*

---

## Phase 2: Multi-Channel (v0.5 — v0.6)

Cíl: Agent dostupný odkudkoli — nejen v terminálu.

### v0.5 — "Anywhere"
- [ ] **WhatsApp integration** — bot přes WhatsApp Business API
- [ ] **Discord bot** — plnohodnotný Discord agent
- [ ] **Slack integration** — workspace bot
- [ ] **REST API** — externí nástroje mohou volat Cell-2
- [ ] **Webhook support** — přijímá webhooks z GitHub, Sentry, atd.
- [ ] **Voice I/O** — Whisper pro STT, TTS pro odpovědi

### v0.6 — "Multi-Modal Brain"
- [ ] **Native vision** — GPT-4V / Claude / Gemini (ne base64 hack)
- [ ] **Better documents** — DOCX, XLSX, nativní PDF parsing
- [ ] **Companion app (macOS)** — menubar access, notifikace
- [ ] **Image understanding** — detekce objektů, koncept matching
- [ ] **Audio messages** — posílá hlasové zprávy na Telegram/WhatsApp

→ *Teď můžeš s agentem komunikovat odkudkoli*

---

## Phase 3: Scale (v1.0)

Cíl: Produkt ready pro široké použití.

### v1.0 — "The Workstation"
- [ ] **Docker support** — celý Cell-2 jako Docker container:
  - `docker run -it cell2` — okamžitý start
  - Persistentní volume pro `memory/`, `context.json`, config
  - Ideální pro serverové nasazení (24/7 agent)
  - Podpora pro docker-compose s Redis/Postgres (future)
- [ ] **Optional GUI** — lehké nativní GUI, TUI zůstává primární
- [ ] **Installer & auto-update** — Windows MSI / macOS DMG / Linux AppImage
- [ ] **Local LLM by default** — llama.cpp nebo similar, cloud je fallback
- [ ] **Encrypted at rest** — šifrování kontextu, paměti, nastavení
- [ ] **Agent marketplace** — sdílení a objevování skill balíčků
- [ ] **Multi-device sync** — E2EE sync mezi telefonem, laptopem, serverem

→ *Teď je to produkt pro normální lidi*

---

## Phase 4: Advanced Features (v1.5+)

Cíl: Enterprise/team funkce a experimentální věci.

### v1.5 — "Ambient Intelligence"
- [ ] **Desktop integration** — clipboard, aktivní okno, notifikace
- [ ] **Proaktivní agent** — surfaceuje relevantní info bez dotazu
- [ ] **Advanced analytics** — analýza tvého chování, produktivity

### v1.6 — "Threads & Team Mode"
- [ ] **Thread system** — izolované chaty pro konkrétní úkoly
  - `/thread new budget-talk` — spawn izolovaného threadu
  - Thread se nepřidává do Space, nezapleveluje kontext
  - Archivace a mazání
- [ ] **Team Mode** — více uživatelů, sdílené session
- [ ] **Personas** — "coding assistant", "researcher", "therapist"
- [ ] **Shared sessions** — dva lidé + agent v jedné konverzaci

→ *Teď to umí i týmovou spolupráci*

---

## The Memory Architecture

Cell's memory is not a dump. It is a **living, layered mind**.

### Space & Chapters

The **Space** is your single, infinite chat — it never resets, never branches, never rolls over. You always pick up where you left off.

Inside that infinite Space, Cell silently breaks the timeline into **chapters**. A chapter is just a stretch of turns separated from the next by a long pause (default: 60 minutes idle). Chapters are *internal* — you don't see them as anything other than a brief `🧠 Session #N closed — captured X memory items` notice when one ends.

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

Classic RAG cannot delete or update. If you say "I drink mango" and later "I drink lemon", RAG stores BOTH. When you ask "what should I drink?", it suggests mango because it was mentioned more often. Cell overwrites facts directly in Semantic layer.

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
