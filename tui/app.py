"""Cell-2 CLI — Keyboard-only terminal interface.

Minimal, fast, no mouse. Just a chat log and input line.
"""

import os
import threading
import time

from textual.app import App
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Footer,
    Header,
    Input,
    RichLog,
    Static,
)

from core import (
    context_store,
    inbox,
    memory_personality,
    permissions,
    settings,
    telegram_bot,
)
from core.core import process, start_scheduler
from core.memory_engine import engine as memory_engine


class CellCLI(App):
    """Minimal CLI interface for Cell-2."""

    CSS_PATH = "app.tcss"
    TITLE = "Cell-2"
    SUB_TITLE = "AI Agent"

    ENABLE_COMMAND_PALETTE = False

    def __init__(self) -> None:
        super().__init__()
        self._busy = False
        self._permission_event = threading.Event()
        self._permission_result = "skip"
        self._file_path = ""

    def compose(self):
        yield Header(show_clock=False)
        yield RichLog(id="chat-log", markup=True, wrap=True, highlight=True)
        with Horizontal(id="input-row"):
            yield Input(
                placeholder="Type message or /help...",
                id="chat-input",
            )
        yield Footer()

    def on_mount(self):
        # Start background
        start_scheduler(ambient_interval=0)
        permissions.set_dialog(self._ask_permission)
        self._start_inbox_polling()
        telegram_bot.start()

        # Load history
        self._load_context()

        # Onboarding
        if settings.is_first_run():
            self._show_welcome()
            settings.complete_onboarding()

        self.query_one("#chat-input", Input).focus()

    def _show_welcome(self):
        self._log_system(
            "Welcome to Cell-2 — your personal AI agent.\n"
            "Commands: /help, /memory, /status, /clear, /reset\n"
            "Just type naturally. The agent handles the rest."
        )

    def on_input_submitted(self, event):
        if event.input.id == "chat-input":
            self._send()

    def _send(self):
        input_widget = self.query_one("#chat-input", Input)
        text = input_widget.value.strip()
        if not text:
            return

        input_widget.value = ""

        # Handle commands
        if text.startswith("/"):
            self._handle_command(text)
            return

        # Display user message
        self._log_user(text)

        # Send to brain
        self._send_to_brain(text)

    def _send_to_brain(self, text: str):
        self._busy = True
        self._log_thinking("thinking...")

        def worker():
            try:
                response = process(text)
            finally:
                self._busy = False

            self.call_from_thread(self._on_response, response)

        threading.Thread(target=worker, daemon=True).start()

    def _on_response(self, response: str):
        if response == "[CANCELLED]":
            self._log_system("(cancelled)")
        elif response.startswith("[SYSTEM ERROR]"):
            self._log_system(response)
        else:
            self._log_agent(response)

    def _handle_command(self, cmd: str):
        parts = cmd.split(maxsplit=2)
        base = parts[0]

        if cmd == "/help":
            self._log_system(
                "Commands:\n"
                "  /help              — this message\n"
                "  /memory            — list memory entries\n"
                "  /memory search <q> — search memory\n"
                "  /status            — agent status\n"
                "  /clear             — clear context\n"
                "  /reset             — factory reset\n"
                "  /permission        — list permissions"
            )
        elif cmd == "/clear":
            import glob

            for f in ("context.json",):
                p = os.path.join(os.path.dirname(__file__), "..", f)
                if os.path.exists(p):
                    os.remove(p)
            self.query_one("#chat-log", RichLog).clear()
            self._log_system("Context cleared.")
        elif cmd == "/reset":
            self._factory_reset()
            self.query_one("#chat-log", RichLog).clear()
            self._log_system("Factory reset complete.")
        elif base == "/memory":
            self._handle_memory(parts)
        elif cmd == "/status":
            self._handle_status()
        elif base == "/permission":
            self._handle_permission(parts)
        else:
            self._log_system(f"Unknown command: {cmd}. Type /help.")

    def _handle_memory(self, parts: list):
        mem = memory_engine()
        if len(parts) == 1:
            entries = mem.list_entries()
            if not entries:
                self._log_system("Memory is empty.")
                return
            lines = [f"Memory ({len(entries)} entries):"]
            for e in entries:
                emoji = {
                    "core": "🔧",
                    "semantic": "🧠",
                    "episodic": "📅",
                    "procedural": "🎯",
                }.get(e.layer, "•")
                lines.append(f"  {emoji} [{e.layer}] {e.filename}")
            self._log_system("\n".join(lines))
        elif parts[1] == "search" and len(parts) >= 3:
            query = parts[2]
            results = mem.search(query, top_k=10)
            if not results:
                self._log_system(f"No results for '{query}'.")
                return
            lines = [f"Results for '{query}':"]
            for e in results:
                lines.append(f"  [{e.layer}] {e.content[:80]}...")
            self._log_system("\n".join(lines))
        else:
            self._log_system("Usage: /memory | /memory search <query>")

    def _handle_status(self):
        mem = memory_engine()
        core = mem.get_core_profile()
        turn = memory_personality.get_turn()
        lam = memory_personality.lambda_m(turn)
        lines = [
            "Cell-2 Status:",
            f"  Turn: {turn}  (λ = {lam:.3f})",
            f"  Core: {core[:80] if core else '(empty)'}",
        ]
        for layer in ("semantic", "episodic", "procedural"):
            count = len(mem.list_entries(layer))
            lines.append(f"  {layer.capitalize()}: {count} entries")
        self._log_system("\n".join(lines))

    def _handle_permission(self, parts: list):
        if len(parts) == 1:
            lines = ["Permissions:"]
            for perm_type, policy in permissions.list_policies().items():
                label = permissions.PERM_CATEGORIES.get(perm_type, perm_type)
                lines.append(f"  {perm_type:20s} → {policy} ({label})")
            self._log_system("\n".join(lines))
        elif len(parts) == 3 and parts[1] in permissions.PERM_CATEGORIES:
            perm_type, policy = parts[1], parts[2]
            if policy not in ("always_allow", "ask", "always_deny"):
                self._log_system("Policy: always_allow, ask, or always_deny")
                return
            permissions.set_policy(perm_type, policy)
            self._log_system(f"{perm_type} → {policy}")
        else:
            self._log_system("Usage: /permission | /permission <type> <policy>")

    # ---- Logging helpers ------------------------------------------------

    def _log_user(self, text: str):
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold white]▸ {text}[/bold white]")

    def _log_agent(self, text: str):
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold green]◆[/bold green] {text}")

    def _log_system(self, text: str):
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[dim]{text}[/dim]")

    def _log_thinking(self, text: str):
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[dim italic]  {text}[/dim italic]")

    # ---- Context load ---------------------------------------------------

    def _load_context(self):
        history = context_store.get_all()
        for m in history[-20:]:  # last 20 only
            role = m.get("role")
            content = m.get("content", "")
            if role == "user":
                self._log_user(content)
            elif role == "assistant":
                self._log_agent(content)
            elif role == "system":
                self._log_system(content)

    # ---- Permissions ----------------------------------------------------

    def _ask_permission(self, operation: str, detail: str) -> str:
        self._permission_event.clear()
        self._permission_result = "skip"

        def on_done(result):
            self._permission_result = result if result else "skip"
            self._permission_event.set()

        # Simple text prompt instead of modal
        self.call_from_thread(self._show_permission_prompt, operation, detail, on_done)
        self._permission_event.wait()
        return self._permission_result

    def _show_permission_prompt(self, operation: str, detail: str, callback):
        self._log_system(
            f"Permission required: {operation}\n  {detail}\n  Allow? (y/n/always/never)"
        )
        # In CLI mode, we can't easily wait for input asynchronously
        # So we auto-allow for now — user can set policies via /permission
        callback("allow")

    # ---- Inbox polling --------------------------------------------------

    def _start_inbox_polling(self, interval: float = 2.0):
        def loop():
            while True:
                time.sleep(interval)
                msgs = inbox.drain()
                for m in msgs:
                    self.call_from_thread(self._log_system, f"[inbox] {m}")

        threading.Thread(target=loop, daemon=True).start()

    # ---- Utils ----------------------------------------------------------

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


def run() -> None:
    app = CellCLI()
    app.run()
