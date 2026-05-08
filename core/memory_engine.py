"""Cell Memory Engine — PersonaVLM four-layer cognitive memory.

Layers:
  Core       — fundamental user attributes (name, identity)        (CRUD, single profile.md)
  Semantic   — event-independent facts, preferences                (CRUD by key)
  Episodic   — atomic time-stamped events from session segments    (append-only)
  Procedural — goals, plans, recurring behaviors                    (CRUD)

Retrieval is delegated to memory_retrieval (sentence-transformer cosine, with
keyword fallback). Personality is owned by memory_personality. This module is
just storage + indexing + age-aware ranking.

Importance decay (per layer):
  core, semantic   → none. Stable facts don't fade.
  procedural       → 0.997^days. Slow. Goals fade only if not refreshed.
  episodic         → 0.99^days. Faster. Old events recede.

There is no remember/forget gate at the engine level. The curator decides what
to write; this engine writes everything it is given.
"""

import json
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any

from core import memory_retrieval

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "memory")
INDEX_FILE = os.path.join(MEMORY_DIR, "index.json")

LAYERS = ("core", "semantic", "episodic", "procedural")

_DECAY_PER_DAY = {
    "core": 1.0,
    "semantic": 1.0,
    "procedural": 0.997,
    "episodic": 0.99,
}

_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(text: str) -> str:
    return re.sub(r"[^\w\-]+", "_", text.lower(), flags=re.UNICODE).strip("_")[:50]


class MemoryEntry:
    """One memory entry, stored as a markdown file with YAML frontmatter."""

    def __init__(
        self,
        layer: str,
        content: str,
        importance: float = 5.0,
        tags: list[str] | None = None,
        key: str = "",
        entry_id: str = "",
        created: str = "",
        updated: str = "",
        source: str = "",
        session_id: int | None = None,
    ) -> None:
        self.layer = layer
        self.content = content
        self.importance = float(importance)
        self.tags = tags or []
        self.key = key
        self.id = entry_id or self._generate_id()
        self.created = created or _now()
        self.updated = updated or self.created
        self.source = source
        self.session_id = session_id

    @staticmethod
    def _generate_id() -> str:
        import uuid

        return str(uuid.uuid4())[:8]

    @property
    def filename(self) -> str:
        if self.layer == "core":
            return "profile.md"
        if self.key:
            return f"{_slugify(self.key)}.md"
        date_prefix = self.created[:10] if self.layer == "episodic" else ""
        slug = _slugify(self.content[:30])
        return f"{date_prefix}_{slug}_{self.id}.md" if date_prefix else f"{slug}_{self.id}.md"

    @property
    def relpath(self) -> str:
        return os.path.join(self.layer, self.filename)

    @property
    def abspath(self) -> str:
        return os.path.join(MEMORY_DIR, self.relpath)

    def to_frontmatter(self) -> str:
        data: dict[str, Any] = {
            "id": self.id,
            "layer": self.layer,
            "created": self.created,
            "updated": self.updated,
            "importance": round(self.importance, 2),
            "tags": self.tags,
            "source": self.source,
        }
        if self.key:
            data["key"] = self.key
        if self.session_id is not None:
            data["session_id"] = self.session_id
        lines = ["---"]
        for k, v in data.items():
            if isinstance(v, list):
                lines.append(f"{k}: [{', '.join(v)}]")
            else:
                lines.append(f"{k}: {v}")
        lines.append("---")
        return "\n".join(lines) + "\n\n" + self.content

    @classmethod
    def from_file(cls, path: str) -> "MemoryEntry | None":
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls.from_text(f.read())
        except Exception:
            return None

    @classmethod
    def from_text(cls, text: str) -> "MemoryEntry":
        if not text.startswith("---"):
            return cls(layer="semantic", content=text.strip())
        parts = text.split("---", 2)
        if len(parts) < 3:
            return cls(layer="semantic", content=text.strip())
        front, content = parts[1].strip(), parts[2].strip()
        data: dict[str, Any] = {}
        for line in front.splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip()
            if v.startswith("[") and v.endswith("]"):
                v = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
            elif v.replace(".", "", 1).replace("-", "", 1).isdigit():
                v = float(v) if "." in v else int(v)
            data[k] = v
        return cls(
            layer=str(data.get("layer", "semantic")),
            content=content,
            importance=float(data.get("importance", 5.0)),
            tags=data.get("tags", []) if isinstance(data.get("tags"), list) else [],
            key=str(data.get("key", "")),
            entry_id=str(data.get("id", "")),
            created=str(data.get("created", "")),
            updated=str(data.get("updated", "")),
            source=str(data.get("source", "")),
            session_id=data.get("session_id") if isinstance(data.get("session_id"), int) else None,
        )


class MemoryEngine:
    """Storage + indexing for the four memory layers."""

    def __init__(self) -> None:
        os.makedirs(MEMORY_DIR, exist_ok=True)
        for layer in LAYERS:
            os.makedirs(os.path.join(MEMORY_DIR, layer), exist_ok=True)
        self._auto_heal_index()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, layer: str, content: str, **kwargs: Any) -> MemoryEntry:
        if layer not in LAYERS:
            raise ValueError(f"Invalid layer: {layer}")
        entry = MemoryEntry(layer=layer, content=content, **kwargs)
        if layer == "core":
            entry.key = "profile"
        self._write(entry)
        self._index_entry(entry)
        return entry

    def read(self, layer: str, filename: str) -> MemoryEntry | None:
        return MemoryEntry.from_file(os.path.join(MEMORY_DIR, layer, filename))

    def update(self, layer: str, filename: str, content: str | None = None, **kwargs: Any) -> MemoryEntry | None:
        entry = self.read(layer, filename)
        if entry is None:
            return None
        if content is not None:
            entry.content = content
        for k, v in kwargs.items():
            if hasattr(entry, k):
                setattr(entry, k, v)
        entry.updated = _now()
        self._write(entry)
        self._index_entry(entry)
        return entry

    def delete(self, layer: str, filename: str) -> bool:
        path = os.path.join(MEMORY_DIR, layer, filename)
        if not os.path.exists(path):
            return False
        entry = self.read(layer, filename)
        os.remove(path)
        if entry:
            memory_retrieval.drop_entry(entry.id)
        self._rebuild_index()
        return True

    def upsert_semantic(
        self,
        key: str,
        content: str,
        importance: float = 5.0,
        tags: list[str] | None = None,
        session_id: int | None = None,
    ) -> MemoryEntry:
        slug = _slugify(key)
        path = os.path.join(MEMORY_DIR, "semantic", f"{slug}.md")
        if os.path.exists(path):
            entry = self.read("semantic", f"{slug}.md")
            if entry:
                entry.content = content
                entry.importance = importance
                entry.tags = tags or entry.tags
                entry.session_id = session_id if session_id is not None else entry.session_id
                entry.updated = _now()
                memory_retrieval.drop_entry(entry.id)  # force re-embed on next query
                self._write(entry)
                self._index_entry(entry)
                return entry
        return self.create(
            "semantic",
            content,
            key=key,
            importance=importance,
            tags=tags or [],
            session_id=session_id,
        )

    def list_entries(self, layer: str | None = None) -> list[MemoryEntry]:
        out: list[MemoryEntry] = []
        layers = [layer] if layer else list(LAYERS)
        for l in layers:
            d = os.path.join(MEMORY_DIR, l)
            if not os.path.exists(d):
                continue
            for fname in sorted(os.listdir(d)):
                if not fname.endswith(".md"):
                    continue
                entry = self.read(l, fname)
                if entry:
                    out.append(entry)
        return out

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def search(self, query: str, layer: str | None = None, top_k: int = 5) -> list[MemoryEntry]:
        pool = self.list_entries(layer)
        if not pool:
            return []
        ranked = memory_retrieval.rank(pool, query, top_k=top_k * 2)
        decayed = [
            (e, score * (self._decay_factor(e) ** 0.25))  # gentle decay tilt
            for e, score in ranked
        ]
        decayed.sort(key=lambda x: -x[1])
        return [e for e, _ in decayed[:top_k]]

    def get_core_profile(self) -> str:
        entry = self.read("core", "profile.md")
        return entry.content if entry else ""

    def get_relevant_for_prompt(self, query: str, top_k: int = 8) -> str:
        from core import memory_personality

        lines: list[str] = []
        core = self.get_core_profile()
        if core:
            lines.append("## Core identity\n" + core)

        lines.append("## Personality profile\n" + memory_personality.summary())

        semantic = self.search(query, layer="semantic", top_k=top_k)
        if semantic:
            lines.append("## Known facts")
            for e in semantic:
                tag = f" [{e.key}]" if e.key else ""
                lines.append(f"-{tag} {e.content}")

        episodic = self.search(query, layer="episodic", top_k=3)
        if episodic:
            lines.append("## Recent events")
            for e in episodic:
                date = e.created[:10] if e.created else "?"
                lines.append(f"- [{date}] {e.content}")

        procedural = self.search(query, layer="procedural", top_k=3)
        if procedural:
            lines.append("## Goals & routines")
            for e in procedural:
                lines.append(f"- {e.content}")

        return "\n\n".join(lines)

    def get_memory_stats(self) -> dict[str, Any]:
        from core import memory_personality, memory_session

        stats: dict[str, Any] = {
            "personality": memory_personality.get(),
            "personality_turn": memory_personality.get_turn(),
            "session": memory_session.current(),
            "embeddings": memory_retrieval.using_embeddings(),
            "layers": {},
        }
        for layer in LAYERS:
            entries = self.list_entries(layer)
            total = sum(e.importance * self._decay_factor(e) for e in entries)
            stats["layers"][layer] = {
                "count": len(entries),
                "weighted_total": round(total, 2),
            }
        return stats

    # ------------------------------------------------------------------
    # Decay
    # ------------------------------------------------------------------

    def _decay_factor(self, entry: MemoryEntry) -> float:
        rate = _DECAY_PER_DAY.get(entry.layer, 1.0)
        if rate >= 1.0:
            return 1.0
        try:
            ref = datetime.fromisoformat(entry.updated or entry.created)
            age = max(0, (datetime.now(timezone.utc) - ref).days)
        except Exception:
            return 1.0
        return rate ** age

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    def _disk_paths(self) -> set[str]:
        out: set[str] = set()
        for layer in LAYERS:
            d = os.path.join(MEMORY_DIR, layer)
            if not os.path.exists(d):
                continue
            for fname in os.listdir(d):
                if fname.endswith(".md"):
                    out.add(f"{layer}/{fname}")
        return out

    def _index_paths(self) -> set[str]:
        idx = self._load_index()
        out: set[str] = set()
        for paths in idx.get("keywords", {}).values():
            for p in paths:
                out.add(p.replace("\\", "/"))
        return out

    def _auto_heal_index(self) -> None:
        """If the index disagrees with disk, rebuild from scratch."""
        if not os.path.exists(INDEX_FILE):
            self._rebuild_index()
            return
        if self._index_paths() != self._disk_paths():
            self._rebuild_index()

    def _load_index(self) -> dict:
        if not os.path.exists(INDEX_FILE):
            return {}
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_index(self, data: dict) -> None:
        with _LOCK:
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def _index_entry(self, entry: MemoryEntry) -> None:
        index = self._load_index()
        keywords = index.setdefault("keywords", {})
        path = entry.relpath.replace("\\", "/")
        for kw, paths in list(keywords.items()):
            if path in paths:
                paths.remove(path)
            if not paths:
                del keywords[kw]
        text = f"{entry.content} {' '.join(entry.tags)} {entry.key}"
        for w in set(_slugify(text).split("_")):
            if len(w) < 2:
                continue
            keywords.setdefault(w, [])
            if path not in keywords[w]:
                keywords[w].append(path)
        index["last_updated"] = _now()
        self._save_index(index)

    def _rebuild_index(self) -> None:
        index: dict[str, Any] = {"keywords": {}, "last_updated": _now()}
        for layer in LAYERS:
            d = os.path.join(MEMORY_DIR, layer)
            if not os.path.exists(d):
                continue
            for fname in os.listdir(d):
                if not fname.endswith(".md"):
                    continue
                entry = self.read(layer, fname)
                if not entry:
                    continue
                path = entry.relpath.replace("\\", "/")
                text = f"{entry.content} {' '.join(entry.tags)} {entry.key}"
                for w in set(_slugify(text).split("_")):
                    if len(w) < 2:
                        continue
                    index["keywords"].setdefault(w, [])
                    if path not in index["keywords"][w]:
                        index["keywords"][w].append(path)
        self._save_index(index)

    def _write(self, entry: MemoryEntry) -> None:
        path = entry.abspath
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with _LOCK:
            with open(path, "w", encoding="utf-8") as f:
                f.write(entry.to_frontmatter())


_engine: MemoryEngine | None = None


def engine() -> MemoryEngine:
    global _engine
    if _engine is None:
        _engine = MemoryEngine()
    return _engine
