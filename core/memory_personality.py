"""PersonaVLM Big Five personality with cosine-decay EMA.

p_m = lambda_m * p_{m-1} + (1 - lambda_m) * p'_m
lambda_m = 0.7 - 0.2 * cos(min(m, 50) / 50 * pi)

Trait scale: 1-5. Update is skipped when the inferred vector is fully neutral (all 3s).
"""

import json
import math
import os
import threading
from datetime import datetime, timezone
from typing import Any

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "memory")
PERSONALITY_FILE = os.path.join(MEMORY_DIR, "personality.json")

TRAITS = ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism")
NEUTRAL = 3.0

_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {
        "openness": NEUTRAL,
        "conscientiousness": NEUTRAL,
        "extraversion": NEUTRAL,
        "agreeableness": NEUTRAL,
        "neuroticism": NEUTRAL,
        "turn": 0,
        "history": [],
        "last_updated": _now(),
    }


def _load() -> dict[str, Any]:
    if not os.path.exists(PERSONALITY_FILE):
        state = _default_state()
        _save(state)
        return state
    try:
        with open(PERSONALITY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for t in TRAITS:
            data.setdefault(t, NEUTRAL)
        data.setdefault("turn", 0)
        data.setdefault("history", [])
        return data
    except Exception:
        return _default_state()


def _save(state: dict[str, Any]) -> None:
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with _LOCK:
        with open(PERSONALITY_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)


def lambda_m(m: int) -> float:
    """λ_m = 0.7 − 0.2·cos(min(m, 50) / 50 · π).

    m=0 → 0.5 (lots of openness to update).
    m≥50 → 0.9 (strongly anchored to history).
    """
    capped = min(max(m, 0), 50)
    return 0.7 - 0.2 * math.cos(capped / 50.0 * math.pi)


def get() -> dict[str, float]:
    state = _load()
    return {t: float(state[t]) for t in TRAITS}


def get_turn() -> int:
    return int(_load().get("turn", 0))


def reset() -> None:
    _save(_default_state())


def update(observed: dict[str, float]) -> dict[str, float] | None:
    """Apply EMA with the cosine-decay lambda.

    `observed` is the inferred trait vector for the current turn (1-5).
    Returns the new state, or None if the update was skipped (all-neutral observation).
    """
    if not observed:
        return None

    obs = {t: float(observed.get(t, NEUTRAL)) for t in TRAITS}
    if all(abs(v - NEUTRAL) < 1e-6 for v in obs.values()):
        return None

    state = _load()
    m = int(state.get("turn", 0))
    lam = lambda_m(m)

    new_state = dict(state)
    for t in TRAITS:
        prev = float(state.get(t, NEUTRAL))
        v = lam * prev + (1.0 - lam) * obs[t]
        new_state[t] = round(max(1.0, min(5.0, v)), 3)

    new_state["turn"] = m + 1
    history = list(state.get("history", []))
    history.append({
        "date": _now(),
        "turn": new_state["turn"],
        "lambda": round(lam, 4),
        **{t: new_state[t] for t in TRAITS},
    })
    new_state["history"] = history[-100:]
    new_state["last_updated"] = _now()

    _save(new_state)
    return {t: new_state[t] for t in TRAITS}


def summary() -> str:
    """One-line natural-language description for the system prompt."""
    p = get()

    def label(value: float, hi: str, lo: str) -> str | None:
        if value >= 3.8:
            return hi
        if value <= 2.2:
            return lo
        return None

    parts: list[str] = []
    for trait, hi, lo in (
        ("openness", "open to new ideas", "prefers the familiar"),
        ("conscientiousness", "organized and goal-directed", "spontaneous and easygoing"),
        ("extraversion", "outgoing and talkative", "reserved and inward"),
        ("agreeableness", "warm and cooperative", "blunt and challenging"),
        ("neuroticism", "emotionally sensitive", "emotionally steady"),
    ):
        l = label(p[trait], hi, lo)
        if l:
            parts.append(l)
    if not parts:
        return "User shows a balanced personality across all five traits."
    return "User is " + ", ".join(parts) + "."
