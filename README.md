# Cell-2

Self-improving AI agent. Starts with one tool (`self_improve`) and writes the rest at runtime as it needs them. Generated tools persist in `brain/functions/` and are reused on the next turn.

## Architecture

```
┌─────────────────────────────────────────┐
│  CORE  (immutable)                      │
│  chat · scheduler · proxy · runner ·    │
│  safety_watchdog · permissions          │
└──────────────────┬──────────────────────┘
                   │  JSON-RPC over stdio
┌──────────────────▼──────────────────────┐
│  BRAIN  (subprocess, sandboxed)         │
│  brain.py + brain/functions/*.py        │
└─────────────────────────────────────────┘
```

| Layer | Role | Mutable by agent |
|-------|------|------------------|
| Core | Chat loop, API client, scheduler, sandbox runner, rollback, permission gate | No |
| Brain | Reasoning loop, runs in its own subprocess | Yes |
| Functions | Generated tools | Grows over time |

Brain runs in a Python subprocess. Its only channel out is `core_rpc` (JSON-RPC over stdio). Calls that touch the host filesystem or shell (`host.read_file`, `host.write_file`, `host.run_command`) require user approval via a permission dialog. If `self_improve` produces a brain.py that fails the smoke test or crashes the subprocess, Core restores from `brain/backup/`.

## Quick start

```bash
git clone https://github.com/yourname/cell-2
cd cell-2
pip install -r requirements.txt
cp config.yaml.example config.yaml
# Edit config.yaml — add your DeepSeek API key
python main.py
```

On first run, `brain/brain.py` is auto-bootstrapped from `brain/brain_factory.py`.

## How a turn runs

1. User sends a message (or a scheduled / ambient task fires).
2. Core assembles the system prompt + history + new message.
3. Core spawns the Brain subprocess and sends an `init` message with the assembled context.
4. Brain calls DeepSeek (`llm.chat` RPC) with its current tool list.
5. The model either:
   - Replies → Brain sends `done`, Core stores the reply.
   - Calls an existing function → executes locally in the subprocess → result back to model.
   - Calls `self_improve(filename, code)` → routed via RPC to Core, validated, backed up, written → callable in this same turn.
   - Calls `host.*` → permission dialog → if allowed, Core executes and returns the result.
6. Loop until the model replies without a tool call (max 25 calls per turn).

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

## Configuration

`config.yaml`:

| Key | Default | Description |
|-----|---------|-------------|
| `deepseek_api_key` | — | DeepSeek API key (required) |
| `ambient_interval_seconds` | `0` | Seconds between autonomous ambient ticks (`0` = off) |

`ASSISTANT.md` (optional, project root): user-defined instructions appended to the system prompt — tone, language, persona, format preferences.

Permission decisions persist in `~/.cell-2/permissions.json`. "Allow always" / "Always deny" are saved per `(operation, target)`; "Allow once" / "Deny" are not. If the dialog times out (15 min), the call is skipped — no decision is saved.

## Project structure

```
cell-2/
├── core/
│   ├── core.py              orchestrator
│   ├── chat.py              system prompt + message assembly
│   ├── proxy.py             DeepSeek API client (holds the key)
│   ├── runner.py            spawns Brain subprocess, drives the RPC loop
│   ├── rpc_server.py        RPC dispatch table
│   ├── permissions.py       host.* permission gate + persistence
│   ├── safety_watchdog.py   smoke tests + rollback chain
│   ├── scheduler.py         scheduled task registry
│   ├── compressor.py        background context summarization
│   ├── context_store.py     append-only history
│   ├── memory_store.py      long-term key/value memory
│   └── inbox.py             background → user messages
│
├── brain/
│   ├── core_rpc.py          RPC client (the only Brain → Core channel)
│   ├── brain_factory.py     factory default (committed)
│   ├── brain.py             live, mutable (gitignored, auto-bootstrapped)
│   ├── functions/           generated tools (gitignored)
│   └── backup/              rolling brain.py snapshots (gitignored)
│
├── main.py                  Textual TUI entrypoint
└── config.yaml.example
```

## Built-in commands

| Command | Effect |
|---------|--------|
| `/help` | Show available commands |
| `/clear` | Clear conversation context |
| `/reset` | Factory reset — clears context, memory, plans, and generated functions; restores `brain.py` from `brain_factory.py` |

## Requirements

- Python 3.11+
- DeepSeek API key — [platform.deepseek.com](https://platform.deepseek.com)
- `ffmpeg` in PATH — only needed if a generated tool processes audio/video. Python deps are installed by the tool itself via `pip` at runtime.

GPU is optional. With an NVIDIA card, install CUDA-enabled PyTorch (`pip install torch --index-url https://download.pytorch.org/whl/cu124`) and any whisper-based tools the agent writes will use it automatically.

## Roadmap

See [TODO.md](TODO.md).

## License

MIT — see [LICENSE](LICENSE).
