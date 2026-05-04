"""Retrieval over memory entries.

Primary path: sentence-transformers (multilingual MiniLM) + numpy cosine.
Fallback (model unavailable): lowercase keyword-overlap with simple stem trimming.

The encoder is loaded lazily on first use and cached for the process lifetime.
Per-entry vectors are cached in memory/embeddings.json keyed by entry id, with a
content hash so stale cache entries are recomputed automatically.
"""

import hashlib
import json
import os
import re
import threading
from typing import Any

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "memory")
CACHE_FILE = os.path.join(MEMORY_DIR, "embeddings.json")

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_LOCK = threading.Lock()
_model = None
_model_failed = False
_cache: dict[str, dict[str, Any]] | None = None


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _load_cache() -> dict[str, dict[str, Any]]:
    global _cache
    if _cache is not None:
        return _cache
    if not os.path.exists(CACHE_FILE):
        _cache = {}
        return _cache
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    except Exception:
        _cache = {}
    return _cache


def _save_cache() -> None:
    if _cache is None:
        return
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with _LOCK:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)


def reset_cache() -> None:
    global _cache
    _cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            os.remove(CACHE_FILE)
        except OSError:
            pass


def _get_model():
    global _model, _model_failed
    if _model is not None or _model_failed:
        return _model
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        _model = SentenceTransformer(MODEL_NAME)
    except Exception:
        _model_failed = True
        _model = None
    return _model


def _encode(text: str) -> list[float] | None:
    model = _get_model()
    if model is None:
        return None
    vec = model.encode([text], normalize_embeddings=True)
    return [float(x) for x in vec[0]]


def _cosine_normed(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def _entry_text(entry: Any) -> str:
    parts = [entry.content or ""]
    if getattr(entry, "key", ""):
        parts.append(entry.key)
    tags = getattr(entry, "tags", None) or []
    if tags:
        parts.append(" ".join(tags))
    return " ".join(parts).strip()


def _embed_entry(entry: Any) -> list[float] | None:
    text = _entry_text(entry)
    if not text:
        return None
    h = _hash(text)
    cache = _load_cache()
    cached = cache.get(entry.id)
    if cached and cached.get("hash") == h and cached.get("vector"):
        return cached["vector"]
    vec = _encode(text)
    if vec is None:
        return None
    cache[entry.id] = {"hash": h, "vector": vec}
    _save_cache()
    return vec


_TOKEN = re.compile(r"[\wÁ-žá-ž]+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    for tok in _TOKEN.findall(text.lower()):
        if len(tok) < 3:
            continue
        out.add(tok)
        if len(tok) > 4:
            out.add(tok[:-1])  # crude stem trim for Czech inflection
            out.add(tok[:-2])
    return out


def _keyword_score(entry: Any, query_tokens: set[str]) -> float:
    text = f"{entry.content} {getattr(entry, 'key', '')} {' '.join(getattr(entry, 'tags', []) or [])}"
    entry_tokens = _tokens(text)
    if not entry_tokens or not query_tokens:
        return 0.0
    overlap = entry_tokens & query_tokens
    if not overlap:
        return 0.0
    return len(overlap) / max(1, len(query_tokens))


def rank(entries: list[Any], query: str, top_k: int = 5, min_score: float = 0.15) -> list[tuple[Any, float]]:
    """Return [(entry, score)] for top_k most relevant entries to the query."""
    if not entries or not query.strip():
        return []

    q_vec = _encode(query)

    if q_vec is not None:
        scored: list[tuple[Any, float]] = []
        for e in entries:
            v = _embed_entry(e)
            if v is None:
                continue
            scored.append((e, _cosine_normed(q_vec, v)))
        scored = [(e, s) for e, s in scored if s >= min_score]
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    # fallback: keyword overlap
    q_tokens = _tokens(query)
    scored = [(e, _keyword_score(e, q_tokens)) for e in entries]
    scored = [(e, s) for e, s in scored if s > 0]
    scored.sort(key=lambda x: -x[1])
    return scored[:top_k]


def drop_entry(entry_id: str) -> None:
    cache = _load_cache()
    if entry_id in cache:
        del cache[entry_id]
        _save_cache()


def using_embeddings() -> bool:
    """True if the encoder loaded successfully on at least one call so far."""
    return _model is not None
