"""Cell TUI — zero-engine terminal interface.

Only dependency for input: blessed Terminal.inkey() for key parsing.
Rendering: pure ANSI escape codes via tui/render.py.
"""

import os
import sys
import threading
import time

from blessed import Terminal

from core import (
    context_store,
    inbox,
    memory_personality,
    scheduler,
    settings,
    telegram_bot,
)
from core.core import _run_ambient_tick, process, start_scheduler, get_smart_request, set_smart_response
from core.memory_engine import engine as memory_engine
from core.runner import cancel_active

from .render import draw_screen, draw_input, draw_dialog


class CellCLI:
    def __init__(self):
        self.term = Terminal()
        self.messages: list[tuple[str, str]] = []
        self.input_buffer = ""
        self.cursor_pos = 0
        self._busy = False
        self._running = True
        self._inbox_queue: list[str] = []
        self._attached_file = ""

    def run(self):
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")

        with self.term.cbreak(), self.term.hidden_cursor():
            start_scheduler()
            self._init_mcp()
            telegram_bot.start()
            self._start_inbox_thread()
            self._load_history()

            if settings.is_first_run():
                self._add_system(
                    "Cell — your personal AI agent. Type /help for commands."
                )
                settings.complete_onboarding()
            else:
                self._add_system("Cell ready.")

            draw_screen(self.messages, self.input_buffer, self._attached_file)

            while self._running:
                key = self.term.inkey(timeout=0.05)
                if key:
                    self._handle_key(key)

                if self._inbox_queue:
                    msg = self._inbox_queue.pop(0)
                    self._add_system(f"[inbox] {msg}")
                    self._redraw()

                req = get_smart_request()
                if req:
                    response = self._run_dialog(req)
                    set_smart_response(response)
                    self._redraw()

    def _run_dialog(self, req):
        label = req["label"]
        prompt = req["prompt"]
        existing = req.get("existing")
        secret = req.get("secret", True)
        buf = ""
        draw_dialog(label, prompt, existing, secret, buf)

        while True:
            key = self.term.inkey()
            if key.name == "KEY_ENTER":
                return buf if buf.strip() else None
            if key.name in ("KEY_ESCAPE",):
                return "__CANCEL__"
            if key == "\x03":
                return "__CANCEL__"
            if key.name in ("KEY_BACKSPACE", "\b"):
                if buf:
                    buf = buf[:-1]
                    draw_dialog(label, prompt, existing, secret, buf)
            elif not key.is_sequence:
                buf += key
                draw_dialog(label, prompt, existing, secret, buf)

    # ── rendering helpers ──────────────────────────────────────

    def _redraw(self):
        draw_screen(self.messages, self.input_buffer, self._attached_file)

    def _redraw_input(self):
        draw_input(self.input_buffer, self._attached_file)

    # ── message helpers ────────────────────────────────────────

    def _add_user(self, text: str):
        self.messages.append(("user", text))

    def _add_system(self, text: str):
        self.messages.append(("system", text))

    # ── background threads ─────────────────────────────────────

    def _start_inbox_thread(self):
        def loop():
            while self._running:
                time.sleep(1.0)
                for m in inbox.drain():
                    self._inbox_queue.append(m)

        threading.Thread(target=loop, daemon=True).start()

    def _load_history(self):
        for m in context_store.get_all()[-50:]:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "user":
                self.messages.append(("user", content))
            elif role == "assistant":
                self.messages.append(("agent", content))
            elif role == "system":
                self.messages.append(("system", content))

    def _init_mcp(self):
        try:
            from core.mcp_client import load_servers
            import yaml

            config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            mcp_configs = cfg.get("mcp_servers")
            if mcp_configs:
                count = load_servers(mcp_configs)
                if count:
                    self._add_system(f"MCP: {count} server(s) connected.")
        except Exception:
            pass

    # ── input handling ─────────────────────────────────────────

    def _handle_key(self, key):
        if key.name == "KEY_ENTER":
            text = self.input_buffer.strip()
            self.input_buffer = ""
            self.cursor_pos = 0
            if text:
                self._process_input(text)
            self._redraw()
        elif key.name in ("KEY_BACKSPACE", "\b"):
            if self.cursor_pos > 0:
                self.input_buffer = (
                    self.input_buffer[: self.cursor_pos - 1]
                    + self.input_buffer[self.cursor_pos :]
                )
                self.cursor_pos -= 1
                self._redraw_input()
        elif key.name in ("KEY_LEFT",):
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
                self._redraw_input()
        elif key.name in ("KEY_RIGHT",):
            if self.cursor_pos < len(self.input_buffer):
                self.cursor_pos += 1
                self._redraw_input()
        elif key.name in ("KEY_HOME",):
            self.cursor_pos = 0
            self._redraw_input()
        elif key.name in ("KEY_END",):
            self.cursor_pos = len(self.input_buffer)
            self._redraw_input()
        elif key.name in ("KEY_DELETE",):
            if self.cursor_pos < len(self.input_buffer):
                self.input_buffer = (
                    self.input_buffer[: self.cursor_pos]
                    + self.input_buffer[self.cursor_pos + 1 :]
                )
                self._redraw_input()
        elif key.name in ("KEY_ESCAPE",):
            if self._busy:
                cancel_active()
                self._add_system("Cancelling...")
                self._redraw()
            else:
                self._running = False
        elif key == "\x03":
            if self._busy:
                cancel_active()
                self._add_system("Cancelling...")
                self._redraw()
            else:
                self._running = False
        elif key.is_sequence:
            pass
        else:
            self.input_buffer = (
                self.input_buffer[: self.cursor_pos]
                + key
                + self.input_buffer[self.cursor_pos :]
            )
            self.cursor_pos += 1
            self._redraw_input()

    # ── input processing ───────────────────────────────────────

    def _process_input(self, text: str):
        if text.startswith("/"):
            self._handle_command(text)
        else:
            self._add_user(text)
            self._redraw()
            self._send_to_brain(text)

    def _send_to_brain(self, text: str):
        self._busy = True
        self._add_system("thinking...")
        self._redraw()

        file_path = self._attached_file
        self._attached_file = ""

        def on_event(msg):
            status = msg
            if msg.startswith("→ "):
                status = msg[2:]
            elif msg.startswith("⏱ "):
                status = msg
            self.messages = [m for m in self.messages if m != ("system", "thinking...")]
            self._add_system(f"thinking... {status}")
            self._redraw()

        def worker():
            try:
                response = process(text, file_path=file_path, on_event=on_event)
            except Exception as e:
                response = f"[SYSTEM ERROR] {e}"
            finally:
                self._busy = False

            self.messages = [
                m
                for m in self.messages
                if m != ("system", "thinking...") and not m[1].startswith("thinking...")
            ]

            if response == "[CANCELLED]":
                self.messages.append(("system", "(cancelled)"))
            elif response.startswith("[SYSTEM ERROR]"):
                self.messages.append(("system", response))
            else:
                self.messages.append(("agent", response))

            self._redraw()

        threading.Thread(target=worker, daemon=True).start()

    # ── commands ───────────────────────────────────────────────

    def _handle_command(self, cmd: str):
        parts = cmd.split(maxsplit=2)
        base = parts[0]

        if cmd == "/help":
            self._add_system(
                "Commands:\n"
                "  /help              — this message\n"
                "  /attach <path>     — attach a file to next message\n"
                "  /edit              — load last message to input for re-editing\n"
                "  /memory            — list memory\n"
                "  /memory search <q> — search memory\n"
                "  /status            — agent status\n"
                "  /clear             — clear context\n"
                "  /reset             — factory reset\n"
                "  /ambient           — show ambient agent status\n"
                "  /ambient on|off|now— toggle proactive agent or tick now\n"
                "  /model             — list available models\n"
                "  /model <name>      — switch to model (e.g. claude-sonnet-4-20250514)\n"
                "  /timings           — show response time stats\n"
                "  /quit              — exit"
            )
        elif base == "/attach":
            path = parts[1] if len(parts) > 1 else ""
            path = os.path.expanduser(path)
            if not path or not os.path.isfile(path):
                self._add_system("Usage: /attach <file_path>")
            else:
                self._attached_file = path
                self._add_system(f"Attached: {os.path.basename(path)}")
        elif cmd == "/edit":
            user_msgs = [(i, m) for i, m in enumerate(self.messages) if m[0] == "user"]
            if not user_msgs:
                self._add_system("No user messages to edit.")
            else:
                _, last = user_msgs[-1]
                self.input_buffer = last[1]
                self.cursor_pos = len(self.input_buffer)
                self._add_system("Last message loaded to input. Press Enter to resend.")
        elif cmd == "/clear":
            for f in ("context.json",):
                p = os.path.join(os.path.dirname(__file__), "..", f)
                if os.path.exists(p):
                    os.remove(p)
            self.messages = []
            self._add_system("Context cleared.")
        elif cmd == "/reset":
            self._factory_reset()
            self.messages = []
            self._add_system("Factory reset complete.")
        elif base == "/memory":
            self._cmd_memory(parts)
        elif cmd == "/status":
            self._cmd_status()
        elif base == "/model":
            self._cmd_model(parts)
        elif cmd == "/quit":
            self._running = False
            return
        elif cmd == "/timings":
            self._cmd_timings()
        else:
            self._add_system(f"Unknown: {cmd}. Type /help.")

        self._redraw()

    # ── command: memory ────────────────────────────────────────

    def _cmd_memory(self, parts: list):
        mem = memory_engine()
        if len(parts) == 1:
            entries = mem.list_entries()
            if not entries:
                self._add_system("Memory is empty.")
                return
            lines = [f"Memory ({len(entries)} entries):"]
            for e in entries:
                emoji = {
                    "core": "C",
                    "semantic": "S",
                    "episodic": "E",
                    "procedural": "P",
                }.get(e.layer, "?")
                lines.append(f"  [{emoji}] {e.filename}")
            self._add_system("\n".join(lines))
        elif parts[1] == "search" and len(parts) >= 3:
            query = parts[2]
            results = mem.search(query, top_k=10)
            if not results:
                self._add_system(f"No results for '{query}'.")
                return
            lines = [f"Results for '{query}':"]
            for e in results:
                lines.append(f"  [{e.layer}] {e.content[:80]}...")
            self._add_system("\n".join(lines))
        else:
            self._add_system("Usage: /memory | /memory search <query>")

    # ── command: status ────────────────────────────────────────

    def _cmd_status(self):
        mem = memory_engine()
        core = mem.get_core_profile()
        turn = memory_personality.get_turn()
        lam = memory_personality.lambda_m(turn)
        lines = [
            "Status:",
            f"  Turn: {turn}  (lambda={lam:.3f})",
            f"  Core: {core[:80] if core else '(empty)'}",
        ]
        for layer in ("semantic", "episodic", "procedural"):
            count = len(mem.list_entries(layer))
            lines.append(f"  {layer.capitalize()}: {count} entries")
        self._add_system("\n".join(lines))

    # ── command: model ─────────────────────────────────────────

    def _cmd_model(self, parts: list):
        from core.proxy import set_model, set_cheap_model
        from core.providers import list_providers as _list_providers

        if len(parts) == 1:
            providers = _list_providers()
            if not providers:
                self._add_system(
                    "No providers configured. Using default from config.yaml."
                )
                return
            lines = ["Available models:"]
            for p in providers:
                lines.append(f"  /model {p}")
            self._add_system("\n".join(lines))
            return
        model_name = parts[1].lower()
        try:
            set_model(model_name)
            self._add_system(f"Model set to '{model_name}'.")
        except Exception as e:
            self._add_system(f"Error: {e}")

    # ── command: timings ───────────────────────────────────────

    def _cmd_timings(self):
        import json
        import os as _os

        path = _os.path.join(_os.path.dirname(__file__), "..", "timings.jsonl")
        if not _os.path.exists(path):
            self._add_system("No timing data yet. Send some messages first.")
            return

        entries = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        if not entries:
            self._add_system("No timing data yet.")
            return

        durs = [e["duration_s"] for e in entries]
        calls = [e["llm_calls"] for e in entries]
        avg_dur = sum(durs) / len(durs)
        max_dur = max(durs)
        min_dur = min(durs)
        avg_calls = sum(calls) / len(calls)

        last5 = entries[-5:]
        lines = [
            f"Response times ({len(entries)} turns)",
            f"  avg: {avg_dur:.1f}s  min: {min_dur:.1f}s  max: {max_dur:.1f}s",
            f"  avg LLM calls: {avg_calls:.1f}",
            "",
            "Last 5 turns:",
        ]
        for e in last5:
            lines.append(
                f"  [{e['ts']}]  {e['duration_s']}s  "
                f"{e['msg_len']}→{e['resp_len']}chars  "
                f"{e['llm_calls']} calls"
            )
        self._add_system("\n".join(lines))

    # ── factory reset ──────────────────────────────────────────

    def _factory_reset(self):
        import glob
        import shutil

        root = os.path.join(os.path.dirname(__file__), "..")
        for f in (
            "context.json",
            "memory.json",
            "schedule.json",
            "summary.json",
            "settings.json",
        ):
            p = os.path.join(root, f)
            if os.path.exists(p):
                os.remove(p)
        functions_dir = os.path.join(root, "core", "functions")
        if os.path.exists(functions_dir):
            for f in glob.glob(os.path.join(functions_dir, "*.py")):
                os.remove(f)
        brain_file = os.path.join(root, "core", "brain.py")
        if os.path.exists(brain_file):
            os.remove(brain_file)
        factory_file = os.path.join(root, "core", "brain_factory.py")
        if os.path.exists(factory_file):
            shutil.copy2(factory_file, brain_file)


def run():
    cli = CellCLI()
    try:
        cli.run()
    except KeyboardInterrupt:
        pass
    print("\nGoodbye.")
