# Cell-2

A self-improving AI agent. Cell-2 can rewrite its own source code, build new tools on demand, and schedule autonomous tasks — all within the hard boundaries of an immutable Core.

## Architecture

```
┌─────────────────────────────┐
│           CORE              │  ← immutable runtime (never rewritten)
│  chat · scheduler · watchdog│
└────────────┬────────────────┘
             │
┌────────────▼────────────────┐
│           BRAIN             │  ← self-modifiable
│  brain.py + functions/      │
└─────────────────────────────┘
```

- **Core** — fixed runtime: context, chat, scheduler, safety watchdog, rollback.
- **Brain** — the agent's live logic. Rewrites itself via `self_improve()`. Starts from `brain_factory.py` on a fresh clone.
- **Functions** — tools the agent builds for itself and calls on future turns (`brain/functions/*.py`).

## Setup

```bash
git clone https://github.com/yourname/cell-2
cd cell-2
pip install -r requirements.txt

cp config.yaml.example config.yaml
# Edit config.yaml and add your DeepSeek API key
```

## Running

```bash
# CLI
python main.py

# TUI (Textual)
python tui.py

# Benchmark
python bench.py
```

## How it works

Each turn the agent receives a user message and a list of tools it has built in previous turns. If it needs a capability that doesn't exist yet, it calls `self_improve()` to write the function, then calls it — all in the same turn.

`brain.py` is the live working file and is gitignored. It is bootstrapped from `brain_factory.py` on first run. `brain/backup/` holds rolling snapshots used for automatic rollback on errors.

## Config

| Key | Description |
|-----|-------------|
| `deepseek_api_key` | DeepSeek API key |
| `ambient_interval_seconds` | Seconds between autonomous ambient ticks (0 = disabled) |

## Requirements

- Python 3.11+
- DeepSeek API key ([platform.deepseek.com](https://platform.deepseek.com))
- ffmpeg (for YouTube transcription)

## License

MIT — see [LICENSE](LICENSE).
