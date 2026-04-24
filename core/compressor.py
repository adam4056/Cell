import json
import os
import tempfile
import threading

from core import context_store, proxy

SUMMARY_FILE = os.path.join(os.path.dirname(__file__), "..", "summary.json")
COMPRESS_THRESHOLD = 60
KEEP_RECENT = 20
_lock = threading.Lock()

_SUMMARIZE_PROMPT = (
    "You are compressing an agent's conversation history to preserve long-term context. "
    "Output a dense, factual summary in third person. Preserve: user identity, stated preferences, "
    "ongoing tasks and their state, decisions made, facts learned, scheduled commitments. "
    "Drop chit-chat, filler, and tool-call minutiae. No headings, no bullet marks — flowing prose."
)


def _load_summary() -> str:
    if not os.path.exists(SUMMARY_FILE):
        return ""
    with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("content", "")


def _save_summary(content: str) -> None:
    d = os.path.dirname(SUMMARY_FILE)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".summary-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"content": content}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SUMMARY_FILE)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def get_summary() -> str:
    with _lock:
        return _load_summary()


def _format_for_llm(msgs: list) -> str:
    lines = []
    for m in msgs:
        role = m.get("role", "?")
        content = m.get("content", "")
        if isinstance(content, list):
            content = json.dumps(content, ensure_ascii=False)
        lines.append(f"[{role}] {content}")
    return "\n".join(lines)


def maybe_compress() -> bool:
    with _lock:
        history = context_store.get_all()
        if len(history) <= COMPRESS_THRESHOLD:
            return False

        to_compress = history[:-KEEP_RECENT]
        recent = history[-KEEP_RECENT:]
        previous = _load_summary()

        messages = [
            {"role": "system", "content": _SUMMARIZE_PROMPT},
            {"role": "user", "content": (
                f"Previous summary (may be empty):\n{previous or '(none)'}\n\n"
                f"New messages to fold in:\n{_format_for_llm(to_compress)}\n\n"
                f"Output the updated summary only."
            )},
        ]

        try:
            new_summary = proxy.chat(messages).get("content", "").strip()
        except Exception:
            return False

        if not new_summary:
            return False

        _save_summary(new_summary)
        context_store.replace_all(recent)
        return True
