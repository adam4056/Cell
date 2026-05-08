"""Cell web server — FastAPI + WebSocket.

Two modes:
  - Space: persistent infinite context (context.json + full memory curation)
  - Chats: isolated threads (chats/{id}.json, no curation)
"""

import asyncio
import glob
import os
import threading
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core import (
    chats_store,
    context_store,
    inbox,
    memory_personality,
    memory_store,
    permissions,
    proxy,
    settings,
)
from core.core import _run_ambient_tick, process, process_chat, start_scheduler
from core.memory_engine import engine as memory_engine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(ROOT, "web", "static")

app = FastAPI(title="Cell")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    token = settings.web_auth_token()
    if not token:
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {token}":
        return await call_next(request)
    if request.url.path.startswith("/api/") or request.url.path == "/ws":
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    return await call_next(request)


_pending_permissions: dict[str, dict] = {}
_perm_events: dict[str, threading.Event] = {}


def _web_permission_dialog(label: str, detail: str) -> str:
    perm_id = os.urandom(8).hex()
    event = threading.Event()
    _perm_events[perm_id] = event
    _pending_permissions[perm_id] = {"label": label, "detail": detail, "id": perm_id}
    if event.wait(timeout=15 * 60):
        result = _pending_permissions.pop(perm_id, {}).get("decision", "deny")
        _perm_events.pop(perm_id, None)
        return result
    _pending_permissions.pop(perm_id, None)
    _perm_events.pop(perm_id, None)
    return "skip"


permissions.set_dialog(_web_permission_dialog)


@app.get("/api/permissions/pending")
def get_pending_permissions():
    return {"pending": list(_pending_permissions.values())}


@app.post("/api/permissions/respond")
def respond_permission(payload: dict):
    perm_id = payload.get("id")
    decision = payload.get("decision", "deny")
    if perm_id in _pending_permissions:
        _pending_permissions[perm_id]["decision"] = decision
        event = _perm_events.pop(perm_id, None)
        if event:
            event.set()
    return {"ok": True}


_pending_permissions: dict[str, dict] = {}
_perm_events: dict[str, threading.Event] = {}


@app.get("/api/chats")
def list_chats():
    return {"chats": chats_store.list_all()}


@app.post("/api/chats")
def new_chat():
    return chats_store.create()


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str):
    return {"deleted": chats_store.delete(chat_id)}


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str):
    chat = chats_store.get(chat_id)
    if chat is None:
        return {"error": "not found"}
    return chat


@app.get("/api/space")
def get_space():
    return {"history": context_store.get_all()}


# ───── Commands API (mirror of TUI slash commands) ─────

ROOT_DIR = ROOT  # alias for clarity


class PermissionUpdate(BaseModel):
    perm_type: str
    policy: str


class AmbientUpdate(BaseModel):
    enabled: bool | None = None
    action: str | None = None


@app.get("/api/commands/status")
def cmd_status():
    mem = memory_engine()
    core = mem.get_core_profile()
    turn = memory_personality.get_turn()
    lam = memory_personality.lambda_m(turn)
    layers = {}
    for layer in ("semantic", "episodic", "procedural"):
        layers[layer] = len(mem.list_entries(layer))
    return {
        "turn": turn,
        "lambda_m": round(lam, 3),
        "core_profile": core or "",
        "layers": layers,
    }


@app.get("/api/commands/memory")
def cmd_memory(q: str | None = None, top_k: int = 10):
    mem = memory_engine()
    if q:
        results = mem.search(q, top_k=top_k)
        return {
            "query": q,
            "results": [
                {"layer": e.layer, "filename": e.filename, "content": e.content}
                for e in results
            ],
        }
    entries = mem.list_entries()
    return {
        "entries": [
            {"layer": e.layer, "filename": e.filename, "content": e.content[:200]}
            for e in entries
        ]
    }


@app.get("/api/commands/permissions")
def cmd_permissions():
    return {
        "policies": [
            {
                "type": t,
                "policy": p,
                "label": permissions.PERM_CATEGORIES.get(t, t),
            }
            for t, p in permissions.list_policies().items()
        ],
        "categories": permissions.PERM_CATEGORIES,
        "valid_policies": ["always_allow", "ask", "always_deny"],
    }


@app.post("/api/commands/permissions")
def cmd_permissions_set(payload: PermissionUpdate):
    if payload.perm_type not in permissions.PERM_CATEGORIES:
        return {"error": f"Unknown permission type: {payload.perm_type}"}
    if payload.policy not in ("always_allow", "ask", "always_deny"):
        return {"error": "Policy must be always_allow, ask, or always_deny"}
    permissions.set_policy(payload.perm_type, payload.policy)
    return {"ok": True, "type": payload.perm_type, "policy": payload.policy}


class ModelUpdate(BaseModel):
    model_name: str


@app.get("/api/commands/model")
def cmd_model_list():
    from core.providers import list_providers as _list_providers

    return {"providers": _list_providers()}


@app.post("/api/commands/model")
def cmd_model_set(payload: ModelUpdate):
    try:
        proxy.set_model(payload.model_name)
        return {"ok": True, "model": payload.model_name}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/commands/ambient")
def cmd_ambient():
    cfg = settings.ambient_config()
    count_today = memory_store.get("ambient.tick_count") or "0"
    tick_date = memory_store.get("ambient.tick_date") or ""
    last_tick = memory_store.get("ambient.last_tick_ts")
    last_min_ago = None
    if last_tick:
        try:
            last_min_ago = int((time.time() - float(last_tick)) / 60)
        except (TypeError, ValueError):
            pass
    return {
        "enabled": cfg.get("enabled"),
        "interval_minutes": cfg.get("interval_minutes"),
        "quiet_hours": cfg.get("quiet_hours") or [0, 0],
        "max_per_day": cfg.get("max_per_day"),
        "cooldown_after_user_min": cfg.get("cooldown_after_user_min"),
        "today_count": count_today,
        "today_date": tick_date,
        "last_tick_min_ago": last_min_ago,
    }


@app.post("/api/commands/ambient")
def cmd_ambient_set(payload: AmbientUpdate):
    if payload.action == "now":
        result = _run_ambient_tick(force=True)
        return {"ok": True, "result": result or "(silent — nothing to do)"}
    settings.set_ambient("enabled", bool(payload.enabled))
    return {"ok": True, "enabled": bool(payload.enabled)}


@app.post("/api/commands/clear")
def cmd_clear():
    p = os.path.join(ROOT_DIR, "context.json")
    if os.path.exists(p):
        os.remove(p)
    return {"ok": True}


@app.post("/api/commands/reset")
def cmd_reset():
    for f in (
        "context.json",
        "memory.json",
        "schedule.json",
        "summary.json",
        "settings.json",
    ):
        p = os.path.join(ROOT_DIR, f)
        if os.path.exists(p):
            os.remove(p)
    functions_dir = os.path.join(ROOT_DIR, "brain", "functions")
    if os.path.exists(functions_dir):
        for f in glob.glob(os.path.join(functions_dir, "*.py")):
            os.remove(f)
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    loop = asyncio.get_running_loop()

    async def push_inbox():
        while True:
            await asyncio.sleep(1.0)
            for msg in inbox.drain():
                try:
                    await ws.send_json({"type": "inbox", "content": msg})
                except Exception:
                    return
            while _pending_permissions:
                _, perm = next(iter(_pending_permissions.items()))
                try:
                    await ws.send_json(
                        {
                            "type": "permission_request",
                            "id": perm["id"],
                            "label": perm["label"],
                            "detail": perm["detail"],
                        }
                    )
                except Exception:
                    return
                await asyncio.sleep(0.5)
                break

    inbox_task = asyncio.create_task(push_inbox())

    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "cancel":
                continue
            mode = data.get("mode", "space")
            text = data.get("text", "")
            chat_id = data.get("chat_id")
            if not text.strip():
                continue

            await ws.send_json({"type": "user_echo", "content": text})
            await ws.send_json({"type": "thinking"})

            def run_turn():
                try:
                    if mode == "chat" and chat_id:
                        return process_chat(chat_id, text)
                    return process(text)
                except Exception as e:
                    return f"[SYSTEM ERROR] {e}"

            output = await loop.run_in_executor(None, run_turn)
            await ws.send_json({"type": "assistant", "content": output})
    except WebSocketDisconnect:
        pass
    finally:
        inbox_task.cancel()


# Static files (mounted last so /api and /ws win)
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    threading.Thread(target=start_scheduler, daemon=True).start()

    try:
        from core.mcp_client import load_servers
        import yaml

        config_path = os.path.join(ROOT, "config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        mcp_configs = cfg.get("mcp_servers")
        if mcp_configs:
            load_servers(mcp_configs)
    except Exception:
        pass

    uvicorn.run(app, host=host, port=port, log_level="warning")
