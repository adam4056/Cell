# Cell

> A self-improving personal AI agent that runs on **your** machine. One agent — code, browse, remember, schedule, talk back. No walled garden.

Cell starts with a single tool (`self_improve`) and writes the rest at runtime as it needs them. Generated tools persist in `core/functions/` and are reused on the next turn. It remembers you across sessions in a four-layer cognitive memory (not a chat dump). It can think proactively in the background. It runs locally.

**Status:** v0.5 — multi-provider (Anthropic / OpenAI / Gemini / DeepSeek / Ollama), native vision, MCP client, ambient agent, four-layer memory.

---

## Quick start

```bash
git clone https://github.com/adam4056/Cell.git
cd Cell
pip install -r requirements.txt
cp config.yaml.example config.yaml
# Edit config.yaml — add at least one provider API key
```

```bash
python main.py          # TUI (terminal interface)
```

That's it. On first run, `core/brain.py` is auto-bootstrapped from `core/brain_factory.py`.

---

## What makes Cell different

- **Self-improving.** The agent writes its own tools. Need a stock price checker? It'll write one — and reuse it next time.
- **Real memory.** Four cognitive layers (Core / Semantic / Episodic / Procedural), Big Five personality with momentum, embedding retrieval. RAG-but-it-can-actually-update.
- **Local-first.** Your data never leaves the machine unless you point it at a cloud LLM. Works fully with local Ollama / llama.cpp.
- **Proactive.** Ambient loop ticks on its own — Cell can surface a goal, notice a pattern, or stay quiet. Anti-spam guards built in.
- **Sandboxed.** Dynamic tools run in a Python sandbox; only `host.*` calls reach your filesystem and they require permission.
- **Multi-provider.** Switch models per turn. Cheap model for curation, smart model for hard turns.
- **MCP-native.** Plug in Model Context Protocol servers (filesystem, GitHub, Gmail, etc.) — they appear as tools automatically.
- **Self-healing.** If `core/brain.py` fails to load, Core restores it from the factory default. Function files are syntax-validated before writing.

---

## Architecture

```
┌─────────────────────────────────────────┐
│  CORE  (single process)                 │
│  orchestrator · proxy · runner ·         │
│  permissions · safety · scheduler        │
│                                          │
│  brain.py  ───  built-in tools          │
│  core_rpc  ───  system services         │
│  functions/ ───  generated tools         │
└─────────────────────────────────────────┘
```

All components run in a single process. The brain imports from `core_rpc` (a thin API layer) for gated system services — memory persistence, scheduling, host filesystem access, LLM calls. Built-in tools live in `core/browser.py`, `core/sandbox.py`, `core/smart_scheduler.py`. Generated tools live in `core/functions/`.

If `self_improve` produces invalid code, Core rejects it with a syntax error. Brain source is immutable at runtime — only new function files are written.

---

## How a turn runs

1. User sends a message (or a scheduled / ambient task fires).
2. Core assembles system prompt + memory retrieval + history + new message.
3. Core calls Brain in-process with the assembled messages.
4. Brain calls the configured provider with its current tool list.
5. The model either:
   - Replies → Core stores the reply.
   - Calls an existing function → executes locally → result back to model.
   - Calls `self_improve(filename, code)` → validated, written to `core/functions/` → callable in this same turn.
   - Calls `host.*` → permission dialog → if allowed, Core executes and returns the result.
6. Loop until the model replies without a tool call (max 25 calls per turn).

After every reply, the curator runs in the background: extracts atomic semantic facts, nudges the Big Five vector. When a chapter closes (60 min idle), it summarizes the stretch into 1–5 episodic events.

---

## Configuration

Edit `config.yaml` — full template in `config.yaml.example`:

```yaml
default_provider: "deepseek"

providers:
  deepseek:
    type: "openai_compat"
    api_base: "https://api.deepseek.com"
    api_key: "sk-..."
    model: "deepseek-chat"
    cheap_model: "deepseek-chat"

  # anthropic, openai, gemini, local Ollama — see config.yaml.example

ambient_interval_seconds: 0   # 0 = off; >0 enables proactive ticks
brave_search_api_key: ""       # optional, for web search
telegram_bot_token: ""         # optional, enables Telegram channel
```

`ASSISTANT.md` (project root, optional): user-defined instructions appended to the system prompt — tone, language, persona, format preferences.

Permission decisions persist in `~/.cell-2/permissions.json`. "Allow always" / "Always deny" are saved per `(operation, target)`. If a dialog times out (15 min), the call is skipped.

---

## Project structure

```
Cell/
├── core/
│   ├── core.py              orchestrator
│   ├── chat.py              system prompt + message assembly
│   ├── brain.py             agent decision loop
│   ├── brain_factory.py     factory default (committed)
│   ├── proxy.py             provider router
│   ├── providers/           anthropic, openai, gemini, openai-compat
│   ├── runner.py            brain runner (in-process)
│   ├── permissions.py       host.* permission gate
│   ├── safety_watchdog.py   smoke tests for brain + functions
│   ├── scheduler.py         scheduled task registry
│   ├── smart_scheduler.py   natural-language schedule parser
│   ├── compressor.py        background context summarization
│   ├── context_store.py     append-only history
│   ├── memory_engine.py     four-layer memory (Core/Semantic/Episodic/Procedural)
│   ├── memory_curator.py    LLM curator (per-turn + per-chapter)
│   ├── memory_personality.py Big Five EMA momentum
│   ├── memory_retrieval.py  embedding + keyword retrieval
│   ├── inbox.py             background → user messages
│   ├── sandbox.py           isolated Python execution
│   ├── browser.py           lightweight fetch + DDG search
│   ├── mcp_client.py        Model Context Protocol client
│   ├── chats_store.py       isolated thread chats
│   ├── telegram_bot.py      Telegram channel
│   ├── functions/           generated tools (gitignored)
│   └── factory_functions/   shipped tools (survive factory reset)
│
├── tui/app.py               blessed-based TUI
├── core_rpc.py              in-process system services API
├── main.py                  TUI entrypoint
└── config.yaml.example
```

---

## Built-in commands

| Command            | Effect                                                                    |
|--------------------|---------------------------------------------------------------------------|
| `/help`            | Show available commands                                                   |
| `/clear`           | Clear conversation context                                                |
| `/model <name>`    | Switch provider/model for this session                                    |
| `/ambient on\|off` | Toggle proactive ambient loop                                             |
| `/ambient now`     | Trigger one ambient tick immediately                                      |
| `/ambient status`  | Show ambient state (last tick, cooldown, daily cap)                       |
| `/schedule <desc>` | Create scheduled task from natural language                               |
| `/memory dreams`   | (planned) Review memory consolidation passes                              |
| `/reset`           | Factory reset — clears context, memory, generated functions; restores brain |

---

## Requirements

- Python 3.11+
- At least one provider API key — DeepSeek, Anthropic, OpenAI, Gemini, or a local Ollama / llama.cpp server
- `ffmpeg` in PATH — only if a generated tool processes audio/video

GPU is optional. With NVIDIA, install CUDA-enabled PyTorch (`pip install torch --index-url https://download.pytorch.org/whl/cu124`) and any whisper-based tools the agent writes will use it automatically.

---

## Roadmap

See [ROADMAP.md](ROADMAP.md). Short version:

- **v0.5** ✓ Multi-provider, vision, MCP, isolated chat threads
- **v0.6** Full browser (Playwright), cost-aware model routing, personality-aware response shaping, image generation
- **v0.7** Subagents, batch processing, Discord/Slack channels, skill marketplace with trust tiers
- **v0.8** Sleep cycle (memory consolidation), self-improve v2 (test-driven + adversarial reviewer), OS-level ambient signals, local fine-tuning, encrypted-at-rest

---

## Contributing

Pick a milestone, open an issue, or just start hacking. The brain is self-improving — your code might teach the agent to write even better code.

## License

MIT — see [LICENSE](LICENSE).
