# Cell — Whitepaper

> *"The Universe is law. The Earth is life."*

---

## 1. Vision

Cell is a self-improving AI agent — a system capable of autonomous operation, expanding its own capabilities, and long-term memory. Unlike static agents (such as Hermes Agent or OpenClaw), Cell can rewrite its own source code, create new functions, and schedule its own tasks — all within fixed boundaries enforced by an immutable system core.

The core analogy: **Universe and Earth.**

- **Universe (Core)** — immutable laws, the physics of the system. It does not care what happens inside. It cannot be rewritten.
- **Earth (Brain)** — a living civilization. It grows, changes, can destroy itself, but can also rebuild itself.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────┐
│                     CORE                        │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐ │
│  │  Chat    │  │ Scheduler│  │Process Manager│ │
│  │  Module  │  │          │  │  (try-except) │ │
│  └────┬─────┘  └────┬─────┘  └───────┬───────┘ │
│       │              │                │         │
│  ┌────▼──────────────▼────────────────▼───────┐ │
│  │              Context Store                 │ │
│  │         (permanent, blockchain-like)       │ │
│  └────────────────────┬───────────────────────┘ │
│                       │                         │
│  ┌────────────────────▼───────────────────────┐ │
│  │                  Proxy                     │ │
│  │       (LLM API communication, keys)        │ │
│  └────────────────────┬───────────────────────┘ │
└───────────────────────┼─────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────┐
│                    BRAIN                        │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │             Main loop                   │   │
│  │  input → LLM → function calling → output│   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  ┌─────────────────┐  ┌──────────────────────┐ │
│  │  Standard       │  │   self_improve()     │ │
│  │  functions      │  │  → routed via Core   │ │
│  │  (local)        │  │                      │ │
│  └─────────────────┘  └──────────────────────┘ │
│                                                 │
│  /brain/                                        │
│    brain.py         ← main logic                │
│    functions/       ← self-generated functions  │
│    assets/          ← arbitrary resources       │
│    backup/          ← snapshots of prior brain  │
└─────────────────────────────────────────────────┘
```

---

## 3. Components

### 3.1 Core

Core is the **system BIOS** — an immutable layer that the brain cannot rewrite under any circumstance. It contains several modules:

#### Chat Module
The user communicates exclusively through Core. Messages are appended to the context, and on every call the full context is passed to the Brain as input.

#### Scheduler
Brain can register scheduled tasks via Core. At the configured time or interval, Core launches Brain with a predefined input and a system message marking it as a scheduled task (rather than a direct user request).

```
Example system message for a scheduled task:
"[SCHEDULED TASK] This is an automatically triggered task: <task description>"
```

#### Process Manager
Core runs Brain inside a protective try-except block:

1. Brain runs.
2. If it completes without error → output is processed normally.
3. If Brain crashes (syntax error, exception, badly generated code):
   - Core performs a **rollback** to the latest functional snapshot from `brain/backup/`.
   - The error (traceback, logs) is written into the context as a system message.
   - On the next run the LLM knows what broke and can fix it.

#### Context Store
The context is **permanent and append-only** — historical steps cannot be overwritten (blockchain-like principle). Each version of the context must be consistent with the previous one. The context contains:
- conversation history with the user,
- system messages (errors, scheduled task notifications),
- function-calling outputs.

> *Note: token-limit handling will be addressed via context compression in a later phase.*

#### Proxy
All communication with the LLM API goes exclusively through the Proxy module in Core. Brain never sees the API key — it only calls `proxy.get(...)`, `proxy.post(...)`, etc. Proxy translates the call into a real HTTP request.

---

### 3.2 Brain

Brain is the **living part of the system** — a code directory that can be rewritten at runtime. Brain is wired to the LLM through the Proxy and runs its own logic, which it designs itself.

#### Main loop

```
input (from Core)
  → processed in brain.py
    → LLM call (via Proxy)
      → function calling
        → output
→ back to Core (stored in context, verified)
```

#### Function Calling

Brain can call functions in two ways:

| Function type | Where it executes | Example |
|---|---|---|
| Standard | Directly in Brain | `get_weather()`, `search_web()` |
| `self_improve()` | Via Core | Rewrite Brain's own source |

Standard functions are generated by Brain itself via `self_improve()` and stored in `brain/functions/`.

#### self_improve()

The key function of the whole system. When the LLM decides it wants a new capability or to fix a bug:

1. It calls `self_improve()` with a description / new code.
2. The call is **routed to Core** (Brain cannot execute it itself).
3. Core performs the change in `brain/`.
4. Before the change, the current state is saved into `brain/backup/`.
5. If the new version fails → automatic rollback (see Process Manager).

Possible variants of `self_improve()`:
- Create a new function
- Modify an existing function
- Rewrite the whole `brain.py`

---

## 4. Security model

| Rule | Reason |
|---|---|
| Brain cannot rewrite Core | Core is the law — breaking it would end the system |
| API keys live only in Core (Proxy) | Brain must not have access to credentials |
| `self_improve()` goes through Core | Core can later add validation, approval, sandboxing |
| Context is append-only | Prevents history manipulation (fraud, reinterpretation) |
| Backup before every change | Guarantees a working state even after a failure |

> *Extended security (sandboxing, process isolation, syscall whitelisting) will be tackled in a later phase.*

---

## 5. Tech stack

| Component | Technology |
|---|---|
| Language | Python |
| LLM | Multi-provider — Anthropic / OpenAI / Gemini / DeepSeek / local |
| LLM communication | Proxy module (Core) |
| Context persistence | File / database (TBD) |
| Task scheduling | Scheduler in Core |

---

## 6. Project structure

```
cell/
├── core/
│   ├── core.py              ← main orchestrator
│   ├── chat.py              ← chat module
│   ├── scheduler.py         ← scheduled task registry
│   ├── runner.py            ← spawns brain, try-except, rollback
│   ├── proxy.py             ← LLM API communication
│   └── context_store.py     ← permanent context store
│
├── brain/
│   ├── brain.py             ← main agent logic
│   ├── functions/           ← self-generated functions
│   ├── assets/              ← arbitrary resources
│   └── backup/              ← snapshots of prior versions
│
├── WHITEPAPER.md
└── README.md
```

---

## 7. Lifecycle of one run

```
1. Trigger (user / scheduler / error recovery)
2. Core assembles input: context + system messages + new input
3. Process Manager runs Brain (try-except)
4. Brain calls the LLM via Proxy
5. The LLM decides on an action:
   a. Reply to user → output to Core
   b. Call a standard function → executed locally in Brain → output to Core
   c. Call self_improve() → Core performs the change → Brain continues
6. Core verifies the output, stores it in the context
7. Output is shown to the user (or stored as a scheduled-task result)
```

---

## 8. Future development

- **Context compression** — automatic summarization of older history to address token limits
- **Extended security layer** — sandbox for the brain, syscall whitelist
- **Multi-brain** — multiple specialized Brain modules coordinated by Core
- **Approval mechanism** — optional user confirmation before `self_improve()`
- **Monitoring dashboard** — overview of state, versions, scheduled tasks

---

*Cell — a system that grows.*
