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
│  │  • Ambient ticks: periodic check-ins                    │   │
│  │  • File watchers: react to changes                  │   │
│  │  • Ambient ticks: proactive suggestions             │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Current State (v0.4)

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
- [x] **Proactive ambient agent** — ambient loop with anti-spam guards (cooldown, quiet hours, daily cap)
- [x] **Ambient state snapshot** in prompt (scheduler tasks, goals, recent events, current time)
- [x] **TUI controls** — `/ambient on|off|status|now`
- [x] **Web UI** — FastAPI + WebSocket, cream pill design, Space/Chats toggle
- [x] **Isolated threads** — `chats_store` + `process_chat()`, no memory curation

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

### v0.4 — "Proactive Agent" ✓ shipped

Cíl: **Cell přestává být reaktivní.** Sám si všimne, sám se ozve, sám něco navrhne.

- [x] **Smart scheduler v2** — přirozený jazyk:
  - "každé ráno shrň maily a ulož do Obsidianu"
  - "každá hodina", "zítra v 15:00", "za 5 minut"
  - `core/smart_scheduler.py` — LLM parsing + heuristic fallback
  - Příkaz: `/schedule <description>`
- [x] **Ambient ticks** — pravidelný tick, který nakopne LLM bez user inputu
  - Loop v `core/core.py` čte interval ze settings při každém ticku (live reload)
  - LLM se rozhodne: *něco říct?* / *něco udělat?* / *mlčet?* (silent return = no-op)
  - Anti-spam guards: cooldown po user msg, quiet hours, daily cap, dedup přes memory_store
  - State persistuje (`ambient.last_tick_ts`, `tick_count`, `tick_date`) — přežije restart
- [x] **Ambient intelligence** — *proaktivní* agent (hlavní cíl v0.4)
  - `build_ambient_input()` injektuje real-time snapshot: `scheduler.list_tasks()`, top procedural goals, recent episodic events, current time
   - Decision layer řízen promptem (proactive: surfacing goals, memory connections, patterns)
  - Doručení přes `inbox.post(...)` → TUI banner / Telegram push
- [x] **TUI ovládání** — `/ambient on|off|status|now`
- [ ] **File watcher triggers** *(nice-to-have, low priority)* — reakce na změny souborů

→ *Cell pracuje, i když u něj nejsi.*

---

## Phase 2: Hermes Parity & Beyond (v0.4.1 — v0.8)

**Strategická pozice:** Hermes Agent (Nous Research) a OpenClaw jsou dnešní laťka pro autonomní AI agenty. Cílem fáze 2 je se s Hermesem nejdřív vyrovnat (v0.5–v0.7) a pak ho předehnat (v0.8) skrze to, co Cell-2 dělá unikátně: čtyřvrstvá paměť, Big Five momentum, Core/Brain isolation s `self_improve`. Před tím malý refaktor (v0.4.1), aby proaktivita byla **opravdu** proaktivní.

### v0.4.1 — "Proactivity" (sjednocení ambient, uvolnění promptu) ✓ shipped

Cíl: zjednodušit model proaktivity a udělat ji opravdovou.

V kódu jsou heartbeat a ambient **už dnes jedna smyčka** (`_run_ambient_tick` v `core/core.py:332` — `/heartbeat` jen volá `_run_ambient_tick(force=True)`). Rozdvojené je to jen v dokumentaci a v UX. Navíc je prompt v `build_ambient_input` (`core/chat.py:286`) moc konzervativní ("act only if genuinely due, missed, or broken... do not invent work, do not greet, do not summarize") — to zabíjí smysl proaktivity.

- [x] **Jeden název: ambient** — heartbeat zmizí z dokumentace i z TUI/Web
  - TUI: `/ambient on|off|status` zůstává; `/ambient now` nahrazuje `/heartbeat`
  - Web UI: jeden ovládací panel, jednotné názvosloví
  - README + ROADMAP: jeden koncept, jedna sekce
- [x] **Loosen the prompt** — `build_ambient_input` v `core/chat.py:286`
  - Odstraněno "Do not invent work, do not greet, do not summarize"
  - Přidána pozitivní instrukce: aktivně surface user-relevant info na základě paměti a vzorů, ne jen čekat na deadline
  - Anti-spam guards (cooldown, quiet hours, daily cap) zůstávají — uvolnění je v *povaze* akce, ne ve frekvenci
- [x] **Proactive triggers** — co všechno smí ambient sám iniciovat
  - Připomenutí goalu z procedural memory ("říkal jsi, že chceš týdně review — uděláme to teď?")
  - Souvislost mezi dnešním kontextem a starší pamětí ("zmínil jsi minulý měsíc X, dnes to může souviset s Y")
  - Návrh next action po dokončení velkého tasku
  - Surface relevantního obsahu z `[AMBIENT]` snapshotu, ne jen reakce na vypršené tasky
- [x] **Predictive ambient** *(přesunuto z v0.8)*
  - Časové vzory: "user každé pondělí v 9:00 řeší maily" → připrav summary předem
  - Anomálie: "user nezaregistroval ranní mail 3 dny" → soft check-in
  - Implementace: frequency tracker v `memory_store` (`ambient.patterns.*`) + detekce v `_ambient_state_snapshot`

→ *Cell se ozve, když má co říct — ne jen když mu něco "uniklo".*

---

### Co dnes chybí oproti Hermes (audit ke 2026-05)

| Oblast | Hermes | Cell-2 dnes |
|---|---|---|
| Multi-model | ano (model-agnostic) | DeepSeek / OpenAI / Anthropic / Gemini / Ollama |
| Vision | nativní | nativní multimodal API |
| MCP klient | ano | `core/mcp_client.py` |
| Browser automation | full (multi-backend) | jen `fetch_url` (statický HTML) |
| Voice I/O | STT + TTS + Discord voice | chybí |
| Subagenty | isolated, parallel | chybí |
| Batch processing | ano | chybí |
| Image generation | ano | chybí |
| Skill marketplace | agentskills.io standard | `self_improve` lokálně, bez sdílení |
| Multi-channel | TG / Discord / Slack / WA / Signal / Email | TUI / TG / Web |

### v0.5 — "Brain Stem" (multi-model + vision + MCP) ✓ shipped

Cíl: rozbít závislost na DeepSeek a otevřít se MCP ekosystému.

- [x] **Multi-provider proxy** — refaktor `core/proxy.py` na adapter pattern
  - Anthropic (Claude 4.x), OpenAI, Gemini, DeepSeek, llama.cpp lokálně
  - Per-turn volba modelu (`/model claude-opus-4-7`)
  - Rozdílné modely pro brain vs. curator (cheap na kuraci, smart na rozhodnutí)
  - BYOK přes `config.yaml`, `~/.cell-2/keys.json`
- [x] **Native vision** — `image/*` MIME jde rovnou do multimodálního API
  - Claude Vision / GPT-4V / Gemini, žádný base64 fallback
  - Nahrazuje `_format_file_attachment` image větev v `core/core.py`
- [x] **MCP klient** — `core/mcp_client.py`
  - Podpora oficiálního `mcp` Pythonského SDK
  - Tools z MCP serverů se automaticky objeví v brain tool listu
  - Per-server konfigurace v `config.yaml` (gh, gmail, fs, atd.)
  - Permission gate respektuje per-server scope

→ *Cell přestává být DeepSeek-only a otevírá se MCP ekosystému.*

### v0.6 — "Hands, Eyes, Voice" (browser, voice, image gen)

Cíl: dohnat Hermes v "akčních" featurách.

- [ ] **Full browser** — `core/browser_full.py` přes Playwright
  - JS rendering, login flows, form filling, screenshot
  - `fetch_url` zůstává jako lightweight default; nový `browse(url, actions=[...])` pro plnou interakci
  - Headless / headed přepínač pro debugging
- [ ] **Voice I/O** *(zvážit odložení za v0.8 — nízká diferenciace, jen catch-up vůči Hermes)*
  - **STT:** Whisper local (CPU+GPU) → text v TUI / Web / Telegram
  - **TTS:** Piper / Coqui → hlasové odpovědi
  - Pozdější: Discord voice channel (live conversation)
- [ ] **Image generation** — `generate_image(prompt)` přes DALL·E / Replicate / lokální Stable Diffusion
- [ ] **Document parsing** — DOCX, XLSX, nativní PDF (`pypdf`, `python-docx`, `openpyxl`)
- [ ] **Audio messages** — Cell pošle voice memo na Telegram / WhatsApp
- [ ] **Cost-aware model routing** — per-turn classifier (trivial / medium / complex) → nejlevnější schopný model
  - Trivial (pozdrav, krátká odpověď) → Haiku / DeepSeek-chat / lokální
  - Medium (běžný turn s memory retrieval) → Sonnet / DeepSeek-reasoner
  - Complex (multi-tool, plánování, `self_improve`) → Opus / GPT-5
  - Klasifikátor: heuristiky (délka, počet tools, klíčová slova) + lehký LLM scorer; cache podle hashů promptu
  - Curator už používá levný model — zobecnit pattern na celý chat; očekávané úspory 5–10× bez ztráty kvality
- [ ] **Personality-aware response shaping** *(přesunuto z v0.8, low effort high impact)*
  - Big Five vektor uživatele řídí styl odpovědi: high Neuroticism → měkčí ton; high Conscientiousness → struktura, bullety
  - Per-uživatelský prompt overlay v `build_input` — žádný velký refaktor, jen vrstva nad systémovým promptem
  - Posiluje feedback loop pro EMA momentum: lepší shaping → přesnější user reactions → přesnější persona

→ *Cell má všechny smysly i ruce, které má Hermes — a navíc volí "kolik mozku" si dovolí.*

### v0.7 — "Subagents & Reach" (paralelizace, kanály, marketplace)

Cíl: paralelní výpočet + dosažitelnost odkudkoli + sdílení skillů.

- [ ] **Subagents** — `runner.spawn_subagent(task, context)`
  - Wrapper nad `run_brain_subprocess` s izolovaným kontextem
  - Vrací výsledek bez kontaminace hlavního turnu
  - Použití: paralelní research, batch zpracování, "delegate to specialist"
- [ ] **Batch processing** — `cell2 batch <prompts.jsonl>` CLI
  - Stovky / tisíce promptů paralelně, JSON output
  - Per-item subagent
- [ ] **Discord bot** — analogie `core/telegram_bot.py`
- [ ] **Slack bot** — workspace integration
- [ ] **WhatsApp** — Business API (později i Signal, iMessage)
- [ ] **Email channel** — IMAP poll + SMTP send
- [ ] **REST API stabilizace** — dokončit `/api/*`, OpenAPI spec
- [ ] **Webhook receivers** — GitHub, Sentry, Linear → ambient triggers
- [ ] **Skill registry**
  - `brain/functions/*.py` → exportovatelný balíček (manifest + deps + spec + hash + autor)
  - Kompatibilita s agentskills.io (pokud spec dovolí)
  - `cell2 skills export <name>` / `cell2 skills install <url>`
  - **Trust tiers** — importovaný skill se nepřidává rovnou do `brain/functions/`
    - Tier 0 (untrusted): běh v izolovaném subprocess, network=deny, fs=read-only sandbox dir
    - Tier 1 (probationary): po N úspěšných runech bez chyby/permission breach se povýší
    - Tier 2 (trusted): manuálně schválené uživatelem, plné permissions per manifest scope
    - Provenance: hash + zdroj URL + datum instalace v `~/.cell-2/skills.json`

→ *Cell-2 == Hermes feature parity.*

### v0.8 — "Beyond Hermes" (diferenciace)

Cíl: využít unikátních silných stránek Cell-2 a předehnat Hermes ve čtyřech osách: paměť, bezpečnost self-improvementu, predikce, lokální AI.

- [ ] **Self-improving brain v2** — `self_improve` jako produkční pipeline, ne hraní
  - **LLM-as-reviewer** — nezávislá instance čte každou navrženou změnu (security, bugs, regrese)
  - **Test-driven** — vygenerovaná funkce **musí** přijít s testem; test běží v sandboxu před merge; fail → starý kód zůstává
  - **Adversarial subagent** — druhá LLM s rolí "red team" zkouší rozbít/prolomit změnu (edge cases, injection, infinite loop)
  - **Regression memory** — historie všeho, co kdy `self_improve` rozbil; injektuje se do promptu reviewera ("tohle už jsi minule rozbil — nezkoušej znova")
  - **Lineage tracking** — každý generovaný tool má parent pointer; periodické pruning obsoletních verzí
- [ ] **Sleep cycle / dream pass** — noční konsolidace paměti *(killer feature, žádný cloud agent to nedělá)*
  - V quiet hours agent projede uzavřené chapters a provede:
    - **Contradiction sweep** — najde rozpory v Semantic ("user pije kávu" vs. "user nepije kávu") a vyřeší přes timestamp + frequency
    - **Redundancy merge** — sloučí duplicitní/podobné fakty (cosine similarity nad embeddings)
    - **Meta-summary** — z N kapitol vygeneruje vyšší abstrakci ("posledních 14 dní user řešil refaktor X")
    - **Goal review** — projede Procedural, označí stagnující/dokončené goaly, navrhne update
  - Implementace: rozšíření `core/memory_curator.py` o `consolidate()` pass; spouští se přes ambient loop v quiet hours, batch over chapters since last consolidation
  - Dream output je vlastní vrstva (`memory/dreams/`), uživatel ji vidí přes `/memory dreams`
- [ ] **OS-level ambient signals** *(přesunuto z v1.5 — bez tohohle je "ambient" jen časovač)*
  - **Clipboard watcher** — když user copy-paste velký text, ambient může zareagovat ("vypadá to jako právní dokument, mám připravit shrnutí?")
  - **Active window observer** — Cell ví, na co se user dívá (PDF, IDE, browser tab) → context bez ptaní
  - **Recent files** — co user otevřel/upravil za poslední hodinu → ambient signal pro proactive trigger
  - Implementace: lehký background daemon (Windows: `pywin32`; macOS: AppleScript / `Quartz`; Linux: `xdotool`/`wmctrl`)
  - Privacy gate: per-app whitelist, klipboard nikdy do trvalé paměti bez explicitního souhlasu
- [ ] **Persona forking** — "coding assistant", "researcher", "therapist" personas
  - Sdílená Core paměť (kdo user je) + per-persona Procedural & Episodic
  - `/persona researcher`
- [ ] **Local fine-tuning** — uživatelská data → osobní LoRA
  - Fine-tune lokální Llama / Qwen na user-specific patterns (data nikdy neopouští stroj)
  - Cell se učí "jak ten konkrétní člověk myslí" — Hermes tohle nedělá
- [ ] **Memory provenance & undo** — každý `memory_engine.add()` má source pointer
  - *"Proč si Cell myslí, že mám alergii na jahody?"* → ukáže větu z konverzace 3 týdny zpět
  - `/memory revert <id>` — undo konkrétní paměti bez narušení sousedů
- [ ] **Encrypted-at-rest by default** — `memory/`, `context.json`, `chats/` šifrované
  - Master passphrase nebo OS keychain
  - Zero-knowledge: bez klíče ani Cell sám nečte staré stavy
- [ ] **Multi-device E2EE sync** — vlastní relay nebo Syncthing wrapper
  - Telefon ↔ laptop ↔ server: stejná persona, stejná paměť
  - Konflikt resolution: "newest semantic, append-merge episodic"

→ *Cell-2 už není kopie Hermes — má hlubší paměť, sleep cycle, bezpečný self-improvement s testy a red-teamem, ambient OS signály a lokální fine-tuning.*

---

## Phase 3: Production (v1.0)

Cíl: produkt ready pro široké použití.

### v1.0 — "The Workstation"
- [ ] **Docker support** — celý Cell-2 jako Docker container
  - `docker run -it cell2` — okamžitý start
  - Persistentní volume pro `memory/`, `context.json`, `chats/`, config
  - Ideální pro 24/7 serverové nasazení; docker-compose s Redis/Postgres
- [ ] **Optional GUI** — lehké nativní GUI; TUI zůstává primární
- [ ] **Installer & auto-update** — Windows MSI / macOS DMG / Linux AppImage
- [ ] **Companion app (macOS)** — menubar access, native notifikace
- [ ] **Local LLM by default** — llama.cpp nebo similar; cloud je fallback
- [ ] **Agent marketplace** — sdílení a objevování skill balíčků (rozšíření v0.7 registry)

→ *Teď je to produkt pro normální lidi.*

---

## Phase 4: Advanced (v1.5+)

### v1.5 — "Ambient Intelligence v2"
- [ ] **Native system notifications** — Cell push přes OS notification center (Windows toast, macOS NC, Linux libnotify)
- [ ] **Advanced analytics** — analýza chování, produktivity, návyků uživatele
- [ ] **Ambient action proposals** — nejen "říct něco", ale "udělat něco" s confirm dialog (např. po copy-paste auto-připrav response template)

### v1.6 — "Team Mode"
- [x] **Thread system** *(shipped in v0.5 web UI)*
- [ ] **Team Mode** — více uživatelů, sdílené session
- [ ] **Shared sessions** — dva lidé + agent v jedné konverzaci

→ *Teď to umí i týmovou spolupráci.*

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
