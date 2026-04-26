# Cell-2

> A self-improving AI agent. Ships with **one** tool — and builds the rest itself.

Cell-2 is an autonomous agent built on the principle that real autonomy means an agent decides what tools it needs, then writes them. There is no fixed toolbox. Ask it to summarize a YouTube video and no transcription tool exists? It writes one in the same turn, then uses it. The next time you ask, the tool is already there.

```
You: Summarize this YouTube video https://youtu.be/xxx

Brain:
  → self_improve: youtube_transcriber.py
  → youtube_transcriber(url=...)
  ← {transcript: "...", duration: 482}

Cell-2:
  The video discusses ...
```

---

## Architecture

```
┌─────────────────────────────────────────┐
│                 CORE                    │  immutable runtime
│  chat · scheduler · proxy · watchdog    │  the agent cannot rewrite this
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│                BRAIN                    │  self-modifiable
│  brain.py + brain/functions/*.py        │  the agent rewrites itself here
└─────────────────────────────────────────┘
```

| Layer | Role | Mutable by agent |
|-------|------|------------------|
| **Core** | BIOS — chat loop, API client, scheduler, safety, rollback | Never |
| **Brain** | Living logic — main reasoning file | Yes |
| **Functions** | Tools the agent has built so far | Grows over time |

The boundary is intentional. Core is law. Brain is life — fragile, mutable, can rebuild itself. If a `self_improve` call breaks Brain, Core auto-rolls back from `brain/backup/`.

---

## Quick start

```bash
git clone https://github.com/yourname/cell-2
cd cell-2
pip install -r requirements.txt
cp config.yaml.example config.yaml
# Edit config.yaml — add your DeepSeek API key
```

Run it:

```bash
python tui.py     # Textual TUI (recommended)
python main.py    # plain CLI
python bench.py   # benchmark vs published baselines
```

On first run, `brain/brain.py` is auto-bootstrapped from `brain/brain_factory.py`.

---

## Features

- **Self-extending toolset** — `self_improve(filename, code)` writes a new function file, callable in the same turn
- **Automatic rollback** — broken brain rewrites are reverted from `brain/backup/`
- **Smoke-tested rewrites** — syntax + import checks before any brain.py rewrite is committed
- **Persistent context** — append-only conversation history with auto-compression
- **Long-term memory** — `memory_store` for facts the agent should remember across sessions
- **Scheduled tasks** — agent registers its own recurring jobs ("check this every Sunday")
- **Ambient mode** — agent can act on its own between user prompts
- **User-defined assistant instructions** — drop an `ASSISTANT.md` in the project root for tone, language, persona

---

## How a turn runs

1. User sends a message (or a scheduled / ambient task fires)
2. Core assembles the system prompt + history + new message
3. Brain calls DeepSeek with the function list it has built so far
4. The model either:
   - Replies → Core stores it, returns to user
   - Calls an existing function → executes locally → result back to model
   - Calls `self_improve(filename, code)` → Core validates → backs up → writes file → callable in this same turn
5. Loop until the model replies without a tool call (max ~25 calls per turn)

Every function file in `brain/functions/` defines:

```python
def run(**kwargs) -> dict | str: ...

SPEC = {
    "description": "...",
    "parameters": {
        "type": "object",
        "properties": {...},
        "required": [...],
    },
}
```

---

## Configuration

`config.yaml`:

| Key | Default | Description |
|-----|---------|-------------|
| `deepseek_api_key` | — | DeepSeek API key (required) |
| `ambient_interval_seconds` | `0` | Seconds between autonomous ambient ticks (`0` = off) |

`ASSISTANT.md` (optional, project root): user-defined instructions appended to the system prompt — tone, language, persona, format preferences.

---

## Project structure

```
cell-2/
├── core/                    immutable runtime
│   ├── core.py              orchestrator
│   ├── chat.py              system prompt + message assembly
│   ├── proxy.py             DeepSeek API client (holds the key)
│   ├── scheduler.py         scheduled task registry
│   ├── safety_watchdog.py   smoke tests + rollback
│   ├── compressor.py        background context summarization
│   ├── context_store.py     append-only history
│   ├── memory_store.py      long-term key/value memory
│   └── inbox.py             background → user messages
│
├── brain/
│   ├── brain_factory.py     factory default (committed)
│   ├── brain.py             live, mutable (gitignored, auto-bootstrapped)
│   ├── functions/           self-generated tools (gitignored)
│   └── backup/              rolling brain.py snapshots (gitignored)
│
├── main.py                  plain CLI entrypoint
├── tui.py                   Textual TUI entrypoint
├── bench.py                 benchmark suite
└── config.yaml.example
```

---

## Built-in commands

Both `main.py` and `tui.py` accept slash commands:

| Command | Effect |
|---------|--------|
| `/help` | Show available commands |
| `/clear` | Clear conversation context |
| `/reset` | Factory reset — clears context, memory, plans, and self-generated functions; restores `brain.py` from `brain_factory.py` |

---

## Requirements

- **Python 3.11+**
- **DeepSeek API key** — sign up at [platform.deepseek.com](https://platform.deepseek.com)
- **`ffmpeg`** in PATH — only if you want the agent to build audio/video tools (it will install Python deps itself via `pip` from inside the function)

GPU is optional. If you have an NVIDIA card, install CUDA-enabled PyTorch (`pip install torch --index-url https://download.pytorch.org/whl/cu124`) and any whisper-based functions the agent writes will use it automatically.

---

## Roadmap

See [TODO.md](TODO.md). Highlights:

- Sandboxed brain execution
- Optional human approval gate before `self_improve()`
- Multi-brain coordination
- Status / monitoring dashboard

---

## Background

Read the full design in [WHITEPAPER.md](WHITEPAPER.md).

The architecture borrows from biology: a fixed core (the cell's BIOS — DNA replication, membrane integrity) and a mutable interior (proteins, behavior). The core is law; everything else is life. Hence the name — Cell-2.

---

## License

MIT — see [LICENSE](LICENSE).
