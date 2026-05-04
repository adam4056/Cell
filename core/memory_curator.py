"""Memory curator — two-stage update per PersonaVLM.

Per-turn (`curate_turn`): runs after every user→assistant exchange.
  - Extracts semantic facts (preferences, attributes) → semantic layer.
  - Infers Big Five vector for this turn → memory_personality.update (cosine-EMA).

Per-session (`curate_session`): runs when the active session closes.
  - Splits session dialogue into atomic time-stamped events → episodic layer.
  - Updates core identity (CRUD) → core layer.
  - Updates goals / routines / habits (CRUD) → procedural layer.

Both stages call the LLM through `proxy.request`. Failures are logged and
swallowed — memory updates are best-effort, never block the user reply.
"""

import json
import os
import re
import threading
import traceback
from typing import Any

from core import inbox, memory_personality, memory_session, proxy
from core.memory_engine import MemoryEngine, engine as memory_engine, _now

_CURATOR_LOG = os.path.join(os.path.dirname(__file__), "..", "memory", "curator.log")
os.makedirs(os.path.dirname(_CURATOR_LOG), exist_ok=True)


def _log(msg: str) -> None:
    try:
        with open(_CURATOR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{_now()}] {msg}\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Per-turn prompt
# ---------------------------------------------------------------------------

_TURN_PROMPT = """You analyze one user→assistant exchange and decide what (if anything) to remember.

USER MESSAGE:
{user_msg}

ASSISTANT REPLY:
{assistant_msg}

Return ONLY this JSON, no prose:
{{
  "semantic_facts": [
    {{"key": "short_snake_case_key", "content": "the fact in the user's language", "importance": 1-10}}
  ],
  "personality_observed": {{
    "openness": 1-5, "conscientiousness": 1-5, "extraversion": 1-5,
    "agreeableness": 1-5, "neuroticism": 1-5
  }}
}}

Rules:
- semantic_facts: ONLY non-trivial preferences / attributes / stable facts about the user. Empty list if none.
- One key per fact (e.g. "name", "diet", "favorite_color", "job_title", "pet"). Snake_case, English keys.
- Content: write in the user's language (Czech if the user speaks Czech, English if English).
- importance: 1-3 trivia, 4-6 normal, 7-10 identity-defining.
- personality_observed: ALL traits 3 (neutral) when the message gives no signal. Score 1-5 (1=very low, 3=neutral, 5=very high).
- Score the USER's traits, not the assistant's.
- Output ONLY the JSON. No markdown fences, no commentary.
"""

# ---------------------------------------------------------------------------
# Per-session prompt
# ---------------------------------------------------------------------------

_SESSION_PROMPT = """You analyze a full conversation session and emit batch updates for long-term memory.

SESSION DIALOGUE:
{dialogue}

Return ONLY this JSON:
{{
  "episodic_events": [
    {{"summary": "one-sentence summary", "keywords": ["k1","k2"], "importance": 1-10}}
  ],
  "core_updates": [
    {{"content": "identity-level fact about who the user is", "importance": 7-10}}
  ],
  "procedural_updates": [
    {{"key": "short_key", "content": "goal / routine / habit", "importance": 1-10}}
  ]
}}

Rules:
- episodic_events: split the session into 1-5 atomic topics. Empty if the session was trivial.
- core_updates: ONLY for fundamental identity (name, profession, location, who they fundamentally are). Skip if nothing identity-level was revealed.
- procedural_updates: explicit goals, ongoing projects, habits, recurring plans. Skip casual one-offs.
- Use the user's language for content (Czech for Czech speakers).
- Output ONLY the JSON. No markdown fences, no commentary.
"""


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    body = m.group(1).strip() if m else text
    start = body.find("{")
    end = body.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(body[start : end + 1])
    except Exception:
        return None


def _llm_json(prompt: str, system: str) -> dict | None:
    try:
        response = proxy.request(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            model=None,
        )
    except Exception:
        _log(f"LLM call failed:\n{traceback.format_exc()}")
        return None
    data = _extract_json(response)
    if data is None:
        _log(f"LLM returned non-JSON: {response[:300]}")
    return data


# ---------------------------------------------------------------------------
# Per-turn curation
# ---------------------------------------------------------------------------

class MemoryCurator:
    def __init__(self, mem: MemoryEngine | None = None) -> None:
        self.mem = mem or memory_engine()

    def curate_turn(self, user_msg: str, assistant_msg: str) -> dict[str, Any]:
        if not user_msg.strip():
            return {"skipped": "empty_user"}

        cur = memory_session.current()
        sid = int(cur["id"]) if cur else None

        prompt = _TURN_PROMPT.format(
            user_msg=user_msg.strip()[:4000],
            assistant_msg=(assistant_msg or "").strip()[:2000],
        )
        data = _llm_json(prompt, "You are a memory extraction engine. Output ONLY valid JSON.")
        if data is None:
            return {"skipped": "llm_no_json"}

        report: dict[str, Any] = {"semantic": [], "personality_updated": False}

        for fact in data.get("semantic_facts") or []:
            key = str(fact.get("key", "")).strip()
            content = str(fact.get("content", "")).strip()
            importance = float(fact.get("importance", 5.0))
            if not key or not content:
                continue
            entry = self.mem.upsert_semantic(
                key=key,
                content=content,
                importance=importance,
                tags=["auto", "turn"],
                session_id=sid,
            )
            report["semantic"].append(f"{key}: {content[:60]}")
            _log(f"semantic upsert key={key} importance={importance} content={content[:80]}")

        observed = data.get("personality_observed") or {}
        new_state = memory_personality.update(observed)
        if new_state is not None:
            report["personality_updated"] = True
            _log(f"personality updated turn={memory_personality.get_turn()} state={new_state}")

        return report

    def curate_session(self, session: dict[str, Any], messages: list[dict[str, Any]]) -> dict[str, Any]:
        sid = int(session.get("id", 0))
        if not messages:
            _log(f"session #{sid} closed but had no messages — skipping")
            return {"skipped": "empty_session"}

        dialogue = self._format_dialogue(messages)
        prompt = _SESSION_PROMPT.format(dialogue=dialogue[:12000])
        data = _llm_json(prompt, "You are a memory extraction engine. Output ONLY valid JSON.")
        if data is None:
            return {"skipped": "llm_no_json"}

        report: dict[str, Any] = {"episodic": [], "core": [], "procedural": []}

        for ev in data.get("episodic_events") or []:
            summary = str(ev.get("summary", "")).strip()
            if not summary:
                continue
            keywords = [str(k).strip() for k in (ev.get("keywords") or []) if str(k).strip()]
            self.mem.create(
                "episodic",
                summary,
                importance=float(ev.get("importance", 5.0)),
                tags=keywords[:8] or ["auto"],
                session_id=sid,
                source="session_curator",
            )
            report["episodic"].append(summary[:60])

        for cu in data.get("core_updates") or []:
            content = str(cu.get("content", "")).strip()
            if not content:
                continue
            existing = self.mem.read("core", "profile.md")
            if existing:
                if content in existing.content:
                    continue
                self.mem.update(
                    "core", "profile.md",
                    content=(existing.content + "\n" + content).strip(),
                )
            else:
                self.mem.create("core", content, importance=float(cu.get("importance", 8.0)))
            report["core"].append(content[:60])

        for pu in data.get("procedural_updates") or []:
            content = str(pu.get("content", "")).strip()
            if not content:
                continue
            key = str(pu.get("key", "")).strip()
            importance = float(pu.get("importance", 5.0))
            if key:
                slug = re.sub(r"[^\w\-]+", "_", key.lower(), flags=re.UNICODE).strip("_")[:50]
                existing = self.mem.read("procedural", f"{slug}.md")
                if existing:
                    existing.content = content
                    existing.importance = importance
                    existing.updated = _now()
                    existing.session_id = sid
                    from core import memory_retrieval

                    memory_retrieval.drop_entry(existing.id)
                    self.mem._write(existing)  # noqa: SLF001
                    self.mem._index_entry(existing)  # noqa: SLF001
                else:
                    self.mem.create(
                        "procedural", content, key=key, importance=importance,
                        tags=["auto"], session_id=sid,
                    )
            else:
                self.mem.create(
                    "procedural", content, importance=importance, tags=["auto"],
                    session_id=sid,
                )
            report["procedural"].append(content[:60])

        _log(
            f"session #{sid} curated: "
            f"{len(report['episodic'])} episodic, "
            f"{len(report['core'])} core, "
            f"{len(report['procedural'])} procedural"
        )

        try:
            total = sum(len(v) for v in report.values())
            if total:
                inbox.post(f"🧠 Session #{sid} closed — captured {total} memory items")
        except Exception:
            pass

        return report

    @staticmethod
    def _format_dialogue(messages: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    str(p.get("text", p)) if isinstance(p, dict) else str(p) for p in content
                )
            if role in ("user", "assistant"):
                lines.append(f"{role.capitalize()}: {content}")
            elif role == "system":
                lines.append(f"[system note] {content}")
        return "\n".join(lines)


_curator: MemoryCurator | None = None


def curator() -> MemoryCurator:
    global _curator
    if _curator is None:
        _curator = MemoryCurator()
    return _curator


# ---------------------------------------------------------------------------
# Background entry points
# ---------------------------------------------------------------------------

def start_turn_curation(user_msg: str, assistant_msg: str) -> None:
    """Background per-turn curation. Non-blocking; errors are logged."""

    def _run() -> None:
        try:
            curator().curate_turn(user_msg, assistant_msg)
        except Exception:
            _log(f"curate_turn crashed:\n{traceback.format_exc()}")

    threading.Thread(target=_run, daemon=True).start()


def start_session_curation(session: dict[str, Any], messages: list[dict[str, Any]]) -> None:
    """Background per-session curation triggered when a session closes."""

    def _run() -> None:
        try:
            curator().curate_session(session, messages)
        except Exception:
            _log(f"curate_session crashed:\n{traceback.format_exc()}")

    threading.Thread(target=_run, daemon=True).start()
