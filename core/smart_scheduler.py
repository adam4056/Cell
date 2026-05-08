"""Cell-2 Smart Scheduler — Natural language task scheduling.

Extends core scheduler with LLM-based natural language parsing.
User can say: "every morning at 8am" instead of cron syntax.
"""

import re
import time
from datetime import datetime, timedelta
from typing import Any

from core import proxy, scheduler


def _llm_parse(description: str) -> dict[str, Any] | None:
    """Use LLM to parse natural language schedule."""
    prompt = f"""Parse this schedule request into structured format.

Request: "{description}"

Output ONLY JSON in this format:
{{
  "type": "recurring" | "one_shot",
  "interval_seconds": number (for recurring, e.g. 86400 for daily),
  "run_at": "ISO8601" (for one-shot),
  "parsed_description": "clean task description"
}}

Examples:
- "every morning at 8am" → {{"type": "recurring", "interval_seconds": 86400, "parsed_description": "Morning task"}}
- "every hour" → {{"type": "recurring", "interval_seconds": 3600, "parsed_description": "Hourly task"}}
- "tomorrow at 3pm" → {{"type": "one_shot", "run_at": "2026-05-05T15:00:00", "parsed_description": "Task"}}
- "in 5 minutes" → {{"type": "one_shot", "run_at": "2026-05-04T14:55:00", "parsed_description": "Task"}}

Current time: {datetime.now().isoformat()}
"""
    try:
        response = proxy.request(
            [
                {
                    "role": "system",
                    "content": "You are a schedule parser. Output ONLY valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            cheap=True,
        )
        # Extract JSON
        import json

        start = response.find("{")
        end = response.rfind("}")
        if start != -1 and end != -1:
            return json.loads(response[start : end + 1])
    except Exception:
        pass
    return None


def _heuristic_parse(description: str) -> dict[str, Any] | None:
    """Fallback heuristic parser."""
    text = description.lower()

    # Recurring patterns
    if "every" in text or "každý" in text or "každé" in text:
        interval = 86400  # default daily
        if "hour" in text or "hodin" in text:
            interval = 3600
        elif "minute" in text or "minut" in text:
            match = re.search(r"(\d+)\s*(?:minute|minut)", text)
            interval = int(match.group(1)) * 60 if match else 300
        elif "day" in text or "den" in text or "denně" in text:
            interval = 86400
        elif "week" in text or "týden" in text or "týdně" in text:
            interval = 604800

        return {
            "type": "recurring",
            "interval_seconds": interval,
            "parsed_description": description,
        }

    # One-shot relative time
    if "in " in text:
        match = re.search(r"in\s+(\d+)\s*(minute|minut|hour|hodin|day|den)", text)
        if match:
            num = int(match.group(1))
            unit = match.group(2)
            if unit in ("minute", "minut"):
                delta = timedelta(minutes=num)
            elif unit in ("hour", "hodin"):
                delta = timedelta(hours=num)
            else:
                delta = timedelta(days=num)
            run_at = (datetime.now() + delta).isoformat()
            return {
                "type": "one_shot",
                "run_at": run_at,
                "parsed_description": description,
            }

    # Tomorrow
    if "tomorrow" in text or "zítra" in text:
        run_at = (
            (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0).isoformat()
        )
        return {
            "type": "one_shot",
            "run_at": run_at,
            "parsed_description": description,
        }

    return None


def schedule(description: str, task_id: str | None = None) -> str:
    """Schedule a task from natural language description."""
    # Try LLM first
    parsed = _llm_parse(description)
    if not parsed:
        parsed = _heuristic_parse(description)

    if not parsed:
        return f"[SCHEDULER] Could not parse: '{description}'. Try formats like 'every hour', 'tomorrow at 3pm', 'in 5 minutes'."

    task_id = task_id or f"task_{int(time.time())}"
    parsed_desc = parsed.get("parsed_description", description)

    if parsed["type"] == "recurring":
        return scheduler.add(
            task_id, parsed_desc, interval_seconds=parsed["interval_seconds"]
        )
    else:
        return scheduler.add(task_id, parsed_desc, run_at=parsed["run_at"])


def natural_language_schedule(user_input: str) -> str:
    """Extract schedule intent from user message and schedule it."""
    # Simple intent detection
    schedule_keywords = [
        "remind me",
        "schedule",
        "every",
        "daily",
        "weekly",
        "hourly",
        "tomorrow",
        "next week",
        "in ",
        "at ",
        "každý",
        "každé",
        "zítra",
        "připomeň",
        "naplánuj",
        "každý den",
        "každé ráno",
    ]

    text_lower = user_input.lower()
    is_schedule = any(kw in text_lower for kw in schedule_keywords)

    if not is_schedule:
        return ""

    return schedule(user_input)
