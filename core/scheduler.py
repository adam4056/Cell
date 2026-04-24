import datetime
import json
import os
import tempfile
import time
import threading

SCHEDULE_FILE = os.path.join(os.path.dirname(__file__), "..", "schedule.json")
_lock = threading.Lock()


def _load() -> list:
    if not os.path.exists(SCHEDULE_FILE):
        return []
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(tasks: list) -> None:
    d = os.path.dirname(SCHEDULE_FILE)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".schedule-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SCHEDULE_FILE)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _parse_iso(run_at: str) -> float:
    dt = datetime.datetime.fromisoformat(run_at)
    if dt.tzinfo is None:
        return dt.timestamp()
    return dt.timestamp()


def add(task_id: str, description: str, interval_seconds: int | None = None, run_at: str | None = None) -> str:
    if (interval_seconds is None) == (run_at is None):
        return "[SCHEDULER ERROR] provide exactly one of interval_seconds or run_at"

    with _lock:
        tasks = _load()
        tasks = [t for t in tasks if t["id"] != task_id]
        if interval_seconds is not None:
            tasks.append({
                "id": task_id,
                "description": description,
                "interval_seconds": int(interval_seconds),
                "next_run": time.time() + int(interval_seconds),
                "one_shot": False,
            })
            _save(tasks)
            return f"[SCHEDULER] task '{task_id}' registered, interval {interval_seconds}s"
        else:
            try:
                fire = _parse_iso(run_at)
            except ValueError as e:
                return f"[SCHEDULER ERROR] invalid run_at: {e}"
            tasks.append({
                "id": task_id,
                "description": description,
                "run_at": run_at,
                "next_run": fire,
                "one_shot": True,
            })
            _save(tasks)
            return f"[SCHEDULER] one-shot task '{task_id}' scheduled at {run_at}"


def remove(task_id: str) -> str:
    with _lock:
        tasks = _load()
        before = len(tasks)
        tasks = [t for t in tasks if t["id"] != task_id]
        _save(tasks)
    return f"[SCHEDULER] task '{task_id}' removed" if len(tasks) < before else f"[SCHEDULER] task '{task_id}' not found"


def get_due() -> list:
    now = time.time()
    with _lock:
        tasks = _load()
        due = []
        kept = []
        for t in tasks:
            if now >= t["next_run"]:
                due.append(t)
                if t.get("one_shot"):
                    continue
                t["next_run"] = now + t["interval_seconds"]
            kept.append(t)
        _save(kept)
    return due


def list_tasks() -> list:
    return _load()
