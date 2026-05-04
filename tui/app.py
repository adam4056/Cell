"""Cell-2 CLI — Traditional terminal interface using blessed.

Pure text, no GUI widgets. Like irssi or weechat.
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
    permissions,
    scheduler,
    settings,
    telegram_bot,
)
from core.core import process, start_scheduler
from core.memory_engine import engine as memory_engine


class CellCLI:
    """Traditional CLI chat interface."""

    def __init__(self):
        self.term = Terminal()
        self.messages: list[tuple[str, str]] = []  # (role, content)
        self.input_buffer = ""
        self.cursor_pos = 0
        self._busy = False
        self._running = True
        self._inbox_queue: list[str] = []

    def run(self):
        import sys

        # Force UTF-8 on Windows
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")

        with self.term.cbreak(), self.term.hidden_cursor():
            # Start background
            start_scheduler(ambient_interval=0)
            permissions.set_dialog(self._ask_permission)
            telegram_bot.start()
            self._start_inbox_thread()
            self._load_history()

            # Welcome
            if settings.is_first_run():
                self._add_system(
                    "Cell-2 — your personal AI agent. Type /help for commands."
                )
                settings.complete_onboarding()
            else:
                self._add_system("Cell-2 ready.")

            self._draw()

            while self._running:
                key = self.term.inkey(timeout=0.05)
                if key:
                    self._handle_key(key)

                # Check inbox
                if self._inbox_queue:
                    msg = self._inbox_queue.pop(0)
                    self._add_system(f"[inbox] {msg}")
                    self._draw()

    def _start_inbox_thread(self):
        def loop():
            while self._running:
                time.sleep(1.0)
                msgs = inbox.drain()
                for m in msgs:
                    self._inbox_queue.append(m)

        threading.Thread(target=loop, daemon=True).start()

    def _load_history(self):
        history = context_store.get_all()
        for m in history[-50:]:  # last 50
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "user":
                self.messages.append(("user", content))
            elif role == "assistant":
                self.messages.append(("agent", content))
            elif role == "system":
                self.messages.append(("system", content))

    def _handle_key(self, key):
        if key.name == "KEY_ENTER":
            text = self.input_buffer.strip()
            self.input_buffer = ""
            self.cursor_pos = 0
            if text:
                self._process_input(text)
            self._draw()
        elif key.name == "KEY_BACKSPACE" or key == "\b":
            if self.cursor_pos > 0:
                self.input_buffer = (
                    self.input_buffer[: self.cursor_pos - 1]
                    + self.input_buffer[self.cursor_pos :]
                )
                self.cursor_pos -= 1
                self._draw()
        elif key.name == "KEY_LEFT":
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
                self._draw()
        elif key.name == "KEY_RIGHT":
            if self.cursor_pos < len(self.input_buffer):
                self.cursor_pos += 1
                self._draw()
        elif key.name == "KEY_HOME":
            self.cursor_pos = 0
            self._draw()
        elif key.name == "KEY_END":
            self.cursor_pos = len(self.input_buffer)
            self._draw()
        elif key.name == "KEY_DELETE":
            if self.cursor_pos < len(self.input_buffer):
                self.input_buffer = (
                    self.input_buffer[: self.cursor_pos]
                    + self.input_buffer[self.cursor_pos + 1 :]
                )
                self._draw()
        elif key.name == "KEY_ESCAPE" or (key == "c" and key.ctrl):
            self._running = False
        elif key.is_sequence:
            pass  # ignore other special keys
        else:
            self.input_buffer = (
                self.input_buffer[: self.cursor_pos]
                + key
                + self.input_buffer[self.cursor_pos :]
            )
            self.cursor_pos += 1
            self._draw()

    def _process_input(self, text: str):
        if text.startswith("/"):
            self._handle_command(text)
        else:
            self._add_user(text)
            self._send_to_brain(text)

    def _send_to_brain(self, text: str):
        self._busy = True
        self._add_system("thinking...")
        self._draw()

        def worker():
            try:
                response = process(text)
            except Exception as e:
                response = f"[SYSTEM ERROR] {e}"
            finally:
                self._busy = False

            # Remove "thinking..." message
            self.messages = [m for m in self.messages if m != ("system", "thinking...")]

            if response == "[CANCELLED]":
                self.messages.append(("system", "(cancelled)"))
            elif response.startswith("[SYSTEM ERROR]"):
                self.messages.append(("system", response))
            else:
                self.messages.append(("agent", response))

            self._draw()

        threading.Thread(target=worker, daemon=True).start()

    def _handle_command(self, cmd: str):
        parts = cmd.split(maxsplit=2)
        base = parts[0]

        if cmd == "/help":
            self._add_system(
                "Commands:\n"
                "  /help              — this message\n"
                "  /memory            — list memory\n"
                "  /memory search <q> — search memory\n"
                "  /status            — agent status\n"
                "  /clear             — clear context\n"
                "  /reset             — factory reset\n"
                "  /permission        — list permissions\n"
                "  /permission <t> <p>— set policy (always_allow/ask/always_deny)\n"
                "  /quit              — exit"
            )
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
        elif base == "/permission":
            self._cmd_permission(parts)
        elif cmd == "/quit":
            self._running = False
            return
        else:
            self._add_system(f"Unknown: {cmd}. Type /help.")

        self._draw()

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

    def _cmd_permission(self, parts: list):
        if len(parts) == 1:
            lines = ["Permissions:"]
            for perm_type, policy in permissions.list_policies().items():
                label = permissions.PERM_CATEGORIES.get(perm_type, perm_type)
                lines.append(f"  {perm_type:20s} → {policy} ({label})")
            self._add_system("\n".join(lines))
        elif len(parts) == 3 and parts[1] in permissions.PERM_CATEGORIES:
            perm_type, policy = parts[1], parts[2]
            if policy not in ("always_allow", "ask", "always_deny"):
                self._add_system("Policy: always_allow, ask, or always_deny")
                return
            permissions.set_policy(perm_type, policy)
            self._add_system(f"{perm_type} → {policy}")
        else:
            self._add_system("Usage: /permission | /permission <type> <policy>")

    def _ask_permission(self, operation: str, detail: str) -> str:
        # In CLI mode, auto-allow for now
        return "allow"

    def _add_user(self, text: str):
        self.messages.append(("user", text))
        self._draw()

    def _add_system(self, text: str):
        self.messages.append(("system", text))

    def _draw(self):
        print(self.term.clear, end="")

        height = self.term.height
        width = self.term.width
        log_height = height - 2  # reserve 2 lines for input

        # Calculate which messages to show
        lines: list[tuple[str, str]] = []  # (style, text)
        for role, content in self.messages:
            for line in content.split("\n"):
                # Wrap long lines
                while line:
                    chunk = line[:width]
                    line = line[width:]
                    lines.append((role, chunk))

        # Show last N lines that fit
        visible = lines[-log_height:] if len(lines) > log_height else lines

        y = 0
        for role, text in visible:
            print(self.term.move(y, 0), end="")
            if role == "user":
                print(f"{self.term.bold_white}>{self.term.normal} {text}")
            elif role == "agent":
                print(f"{self.term.bold_green}<{self.term.normal} {text}")
            elif role == "system":
                print(f"{self.term.dim}  {text}{self.term.normal}")
            y += 1

        # Input line
        print(self.term.move(height - 2, 0) + "─" * width)
        print(self.term.move(height - 1, 0), end="")
        print(f"> {self.input_buffer}", end="")
        sys.stdout.flush()

    def _factory_reset(self):
        import glob, shutil

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
        functions_dir = os.path.join(root, "brain", "functions")
        if os.path.exists(functions_dir):
            for f in glob.glob(os.path.join(functions_dir, "*.py")):
                os.remove(f)


def run():
    cli = CellCLI()
    try:
        cli.run()
    except KeyboardInterrupt:
        pass
    print("\nGoodbye.")
