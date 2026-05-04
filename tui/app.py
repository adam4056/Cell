"""Cell-2 TUI — Textual-based terminal interface."""

import json
import os
import threading
import time

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Static,
)

from core import (
    context_store,
    inbox,
    memory_personality,
    memory_retrieval,
    memory_session,
    permissions,
    settings,
    telegram_bot,
)
from core.core import process, start_scheduler
from core.memory_engine import LAYERS, engine as memory_engine


# ---------------------------------------------------------------------------
# Permission modal
# ---------------------------------------------------------------------------


class PermissionModal(ModalScreen):
    """Permission dialog for host.* operations."""

    BINDINGS = [("escape", "close", "Close")]

    def __init__(self, operation: str, detail: str) -> None:
        super().__init__()
        self.operation = operation
        self.detail = detail

    def compose(self) -> ComposeResult:
        with Container(classes="perm-modal"):
            yield Label("Permission required", classes="perm-title")
            yield Label(f"Operation: {self.operation}", classes="perm-op")
            if self.detail:
                yield Label(self.detail, classes="perm-detail")
            with Horizontal(classes="perm-buttons"):
                yield Button("Allow once", variant="primary", id="allow")
                yield Button("Always allow", id="always_allow")
                yield Button("Deny", id="deny")
                yield Button("Always deny", id="always_deny")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)


# ---------------------------------------------------------------------------
# Onboarding wizard
# ---------------------------------------------------------------------------


class OnboardingModal(ModalScreen):
    """First-run onboarding: API configuration."""

    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        with Container(classes="onboarding-modal"):
            yield Label("Welcome to Cell-2", classes="onboarding-title")
            yield Label(
                "Configure your LLM provider. Leave fields empty to use defaults.",
                classes="onboarding-subtitle",
            )
            yield Label(
                "API Base (e.g. https://api.deepseek.com)", classes="field-label"
            )
            yield Input(placeholder="https://api.deepseek.com", id="api_base")
            yield Label("API Key", classes="field-label")
            yield Input(placeholder="sk-...", id="api_key", password=True)
            yield Label("Model (e.g. deepseek-chat)", classes="field-label")
            yield Input(placeholder="deepseek-chat", id="model")
            yield Label("Brave Search API Key (optional)", classes="field-label")
            yield Input(placeholder="BSAp...", id="brave_key", password=True)
            with Horizontal(classes="onboarding-buttons"):
                yield Button("Skip for now", id="skip")
                yield Button("Save & Start", variant="primary", id="save")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            data = {
                "api_base": self.query_one("#api_base", Input).value.strip(),
                "api_key": self.query_one("#api_key", Input).value.strip(),
                "model": self.query_one("#model", Input).value.strip(),
                "brave_search_api_key": self.query_one(
                    "#brave_key", Input
                ).value.strip(),
            }
            self.dismiss(data)
        else:
            self.dismiss(None)


# ---------------------------------------------------------------------------
# Attach modal
# ---------------------------------------------------------------------------


class AttachModal(ModalScreen):
    """Simple path input for file attachment."""

    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        with Container(classes="attach-modal"):
            yield Label("Attach file", classes="modal-title")
            yield Label("Enter absolute path to file:", classes="modal-subtitle")
            yield Input(placeholder="/home/user/document.pdf", id="attach-path")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Attach", variant="primary", id="attach")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "attach":
            path = self.query_one("#attach-path", Input).value.strip()
            self.dismiss(path if os.path.exists(path) else None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        path = event.value.strip()
        self.dismiss(path if os.path.exists(path) else None)


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------


class CellApp(App):
    """Cell-2 Textual application."""

    CSS_PATH = "app.tcss"
    TITLE = "Cell-2"
    SUB_TITLE = "Self-improving autonomous agent"

    attached_file = reactive("")
    thinking_el = None

    def __init__(self) -> None:
        super().__init__()
        self._busy = False
        self._permission_event = threading.Event()
        self._permission_result = "skip"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(classes="chat-container"):
            yield RichLog(id="chat-log", markup=True, wrap=True, highlight=True)
            # Attachment preview
            with Horizontal(id="attachment-preview", classes="attach-bar"):
                yield Label("📎", classes="attach-icon")
                yield Label("", id="attach-name", classes="attach-name")
                yield Button("✕", id="attach-remove", classes="attach-remove")
            # Input row
            with Horizontal(classes="input-row"):
                yield Button("+", id="attach-btn", classes="input-btn")
                yield Input(placeholder="Ask me anything…", id="chat-input")
                yield Button("⏎", id="send-btn", variant="primary", classes="input-btn")
        yield Footer()

    def on_mount(self) -> None:
        # Start background loops
        ambient = self._load_ambient()
        start_scheduler(ambient_interval=ambient)
        permissions.set_dialog(self._ask_permission)
        self._start_inbox_polling()
        telegram_bot.start()

        # Load context
        self._load_context()

        # Onboarding for first run
        if settings.is_first_run():
            self.push_screen(OnboardingModal(), self._on_onboarding_done)

    # ---- Reactive watch ---------------------------------------------------

    def watch_attached_file(self, path: str) -> None:
        preview = self.query_one("#attachment-preview", Horizontal)
        name_label = self.query_one("#attach-name", Label)
        if path:
            name_label.update(os.path.basename(path))
            preview.styles.display = "block"
        else:
            name_label.update("")
            preview.styles.display = "none"

    # ---- Compose events ---------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            self._send()
        elif event.button.id == "attach-btn":
            self._attach()
        elif event.button.id == "attach-remove":
            self.attached_file = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat-input":
            self._send()

    # ---- Sending ----------------------------------------------------------

    def _send(self) -> None:
        input_widget = self.query_one("#chat-input", Input)
        text = input_widget.value.strip()
        file_path = self.attached_file

        if not text and not file_path:
            return

        self.attached_file = ""
        input_widget.value = ""

        display = text
        if file_path:
            display = (
                f"[📎 {os.path.basename(file_path)}] {text}"
                if text
                else f"[📎 {os.path.basename(file_path)}]"
            )

        self._add_user_message(display)
        self.send_to_brain(text, file_path)

    def _attach(self) -> None:
        def on_done(path: str | None) -> None:
            if path:
                self.attached_file = path

        self.push_screen(AttachModal(), on_done)

    # ---- Brain ------------------------------------------------------------

    def send_to_brain(self, text: str, file_path: str = "") -> None:
        if text.startswith("/") and not file_path:
            self._handle_command(text)
            return

        self.set_thinking("thinking...")
        self._busy = True

        def worker() -> None:
            events: list[str] = []

            def on_event(msg: str) -> None:
                events.append(msg)
                self.call_from_thread(self.set_thinking, "\n".join(events[-5:]))

            response = "[SYSTEM ERROR] Process failed"
            try:
                response = process(text, file_path=file_path, on_event=on_event)
            finally:
                self._busy = False
                self.call_from_thread(self._on_brain_done, response)

        threading.Thread(target=worker, daemon=True).start()

    def _on_brain_done(self, response: str) -> None:
        if response == "[CANCELLED]":
            self.add_system_message("(response cancelled)")
        elif response.startswith("[SYSTEM ERROR]"):
            self.add_system_message(response)
        else:
            self.add_agent_message(response)

    # ---- Commands ---------------------------------------------------------

    def _handle_command(self, cmd: str) -> None:
        parts = cmd.split(maxsplit=2)
        base = parts[0]

        if cmd == "/help":
            lines = "\n".join(f"  {k} — {v}" for k, v in COMMANDS.items())
            self.add_system_message(f"Commands:\n{lines}")
        elif cmd == "/clear":
            import glob

            for f in ("context.json",):
                p = os.path.join(os.path.dirname(__file__), "..", f)
                if os.path.exists(p):
                    os.remove(p)
            self.query_one("#chat-log", RichLog).clear()
            self.add_system_message("Context cleared.")
        elif cmd == "/reset":
            self._factory_reset()
            self.query_one("#chat-log", RichLog).clear()
            self.add_system_message("Factory reset complete.")
        elif base == "/memory":
            self._handle_memory_command(parts)
        elif cmd == "/status":
            self._handle_status_command()
        elif base == "/sandbox":
            self._handle_sandbox_command(parts)
        elif base == "/fetch":
            self._handle_fetch_command(parts)
        elif base == "/permission":
            self._handle_permission_command(parts)
        else:
            self.add_system_message(f"Unknown command: {cmd}. Type /help.")

    def _handle_memory_command(self, parts: list) -> None:
        mem = memory_engine()
        if len(parts) == 1:
            entries = mem.list_entries()
            if not entries:
                self.add_system_message("Memory is empty.")
                return
            lines = [f"Memory ({len(entries)} entries):"]
            for e in entries:
                layer_emoji = {
                    "core": "🔧",
                    "semantic": "🧠",
                    "episodic": "📅",
                    "procedural": "🎯",
                }.get(e.layer, "•")
                lines.append(
                    f"  {layer_emoji} [{e.layer}] {e.filename} (importance: {e.importance})"
                )
            self.add_system_message("\n".join(lines))
        elif parts[1] == "search" and len(parts) >= 3:
            query = parts[2]
            results = mem.search(query, top_k=10)
            if not results:
                self.add_system_message(f"No memory found for '{query}'.")
                return
            lines = [f"Search results for '{query}':"]
            for e in results:
                layer_emoji = {
                    "core": "🔧",
                    "semantic": "🧠",
                    "episodic": "📅",
                    "procedural": "🎯",
                }.get(e.layer, "•")
                lines.append(f"  {layer_emoji} [{e.layer}] {e.content[:80]}...")
            self.add_system_message("\n".join(lines))
        elif parts[1] == "add" and len(parts) >= 3:
            subparts = parts[2].split(maxsplit=1)
            if len(subparts) < 2:
                self.add_system_message("Usage: /memory add <layer> <content>")
                return
            layer, content = subparts
            if layer not in ("core", "semantic", "episodic", "procedural"):
                self.add_system_message(
                    f"Invalid layer: {layer}. Use: core, semantic, episodic, procedural"
                )
                return
            entry = mem.create(layer, content, importance=5.0)
            self.add_system_message(f"✓ Added to {layer}: {entry.filename}")
        elif parts[1] == "delete" and len(parts) >= 3:
            subparts = parts[2].split(maxsplit=1)
            if len(subparts) < 2:
                self.add_system_message("Usage: /memory delete <layer> <filename>")
                return
            layer, filename = subparts
            ok = mem.delete(layer, filename)
            if ok:
                self.add_system_message(f"✓ Deleted {layer}/{filename}")
            else:
                self.add_system_message(f"✗ Not found: {layer}/{filename}")
        elif parts[1] == "personality":
            p = memory_personality.get()
            turn = memory_personality.get_turn()
            lam = memory_personality.lambda_m(turn)
            lines = [
                f"Personality (turn {turn}, λ={lam:.3f}):",
                f"  openness:          {p['openness']:.2f}",
                f"  conscientiousness: {p['conscientiousness']:.2f}",
                f"  extraversion:      {p['extraversion']:.2f}",
                f"  agreeableness:     {p['agreeableness']:.2f}",
                f"  neuroticism:       {p['neuroticism']:.2f}",
                f"  → {memory_personality.summary()}",
            ]
            self.add_system_message("\n".join(lines))
        elif parts[1] == "session":
            cur = memory_session.current()
            if not cur:
                self.add_system_message("No active session.")
            else:
                self.add_system_message(
                    f"Session #{cur['id']}: started {cur['started_at']}, "
                    f"last turn {cur['last_turn_at']}, turns={cur['turn_count']}"
                )
        elif parts[1] == "end-session":
            closed = memory_session.finalize(reason="user_command")
            if closed:
                self.add_system_message(f"Session #{closed['id']} closed.")
            else:
                self.add_system_message("No active session to close.")
        else:
            self.add_system_message(
                "Memory commands:\n"
                "  /memory\n"
                "  /memory search <query>\n"
                "  /memory add <layer> <content>\n"
                "  /memory delete <layer> <filename>\n"
                "  /memory personality\n"
                "  /memory session\n"
                "  /memory end-session"
            )

    def _handle_status_command(self) -> None:
        mem = memory_engine()
        core = mem.get_core_profile()
        turn = memory_personality.get_turn()
        lam = memory_personality.lambda_m(turn)
        cur = memory_session.current()
        lines = [
            "Cell-2 status:",
            f"  Personality turns: {turn}  (λ_m = {lam:.3f})",
            f"  Active session:    "
            + (f"#{cur['id']} ({cur['turn_count']} turns)" if cur else "(none)"),
            f"  Embeddings:        {'on' if memory_retrieval.using_embeddings() else 'keyword fallback'}",
            f"  Core profile:      {core[:100] if core else '(empty)'}",
        ]
        for layer in ("semantic", "episodic", "procedural"):
            entries = mem.list_entries(layer)
            lines.append(f"  {layer.capitalize()} entries: {len(entries)}")
        self.add_system_message("\n".join(lines))

    def _handle_permission_command(self, parts: list) -> None:
        if len(parts) == 1:
            lines = ["Permission policies:"]
            for perm_type, policy in permissions.list_policies().items():
                label = permissions.PERM_CATEGORIES.get(perm_type, perm_type)
                lines.append(f"  {perm_type:20s} → {policy:12s} ({label})")
            self.add_system_message("\n".join(lines))
        elif len(parts) == 3 and parts[1] in permissions.PERM_CATEGORIES:
            perm_type = parts[1]
            policy = parts[2]
            if policy not in ("always_allow", "ask", "always_deny"):
                self.add_system_message(
                    "Policy must be: always_allow, ask, or always_deny"
                )
                return
            permissions.set_policy(perm_type, policy)
            self.add_system_message(f"✓ {perm_type} → {policy}")
        else:
            self.add_system_message(
                "Usage:\n"
                "  /permission                          — list all policies\n"
                "  /permission <type> <policy>          — set policy\n"
                "  /permission reset                    — reset all decisions"
            )

    # ---- Message rendering ------------------------------------------------

    def _add_user_message(self, text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold bright_white]You[/bold bright_white]: {text}")

    def add_agent_message(self, text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold bright_green]Cell[/bold bright_green]: {text}")

    def add_system_message(self, text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[dim italic]{text}[/dim italic]")

    def set_thinking(self, text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[dim]💭 {text}[/dim]")

    # ---- Context load -----------------------------------------------------

    def _load_context(self) -> None:
        history = context_store.get_all()
        for m in history:
            if m.get("role") == "user":
                self._add_user_message(m.get("content", ""))
            elif m.get("role") == "assistant":
                self.add_agent_message(m.get("content", ""))
            elif m.get("role") == "system":
                self.add_system_message(m.get("content", ""))

    # ---- Onboarding -------------------------------------------------------

    def _on_onboarding_done(self, result: dict | None) -> None:
        if result:
            self._update_config(result)
        settings.complete_onboarding()

    def _update_config(self, data: dict) -> None:
        import yaml

        config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        cfg = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        for key in ("api_base", "api_key", "model", "brave_search_api_key"):
            if data.get(key):
                cfg[key] = data[key]
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)

    # ---- Permissions ------------------------------------------------------

    def _ask_permission(self, operation: str, detail: str) -> str:
        self._permission_event.clear()
        self._permission_result = "skip"

        def on_done(result: str | None) -> None:
            self._permission_result = result if result else "skip"
            self._permission_event.set()

        self.call_from_thread(
            self.push_screen, PermissionModal(operation, detail), on_done
        )
        self._permission_event.wait()
        return self._permission_result

    # ---- Inbox polling ----------------------------------------------------

    def _start_inbox_polling(self, interval: float = 1.5) -> None:
        def loop() -> None:
            while True:
                time.sleep(interval)
                msgs = inbox.drain()
                for m in msgs:
                    self.call_from_thread(self.add_system_message, m)

        threading.Thread(target=loop, daemon=True).start()

    # ---- Helpers ----------------------------------------------------------

    def _load_ambient(self) -> int:
        import yaml

        config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return int(yaml.safe_load(f).get("ambient_interval_seconds", 0) or 0)
        return 0

    def _factory_reset(self) -> None:
        import glob, shutil

        root = os.path.join(os.path.dirname(__file__), "..")
        for f in ("context.json", "memory.json", "schedule.json", "summary.json"):
            p = os.path.join(root, f)
            if os.path.exists(p):
                os.remove(p)

        memory_dir = os.path.join(root, "memory")
        if os.path.exists(memory_dir):
            for layer in LAYERS:
                layer_dir = os.path.join(memory_dir, layer)
                if os.path.exists(layer_dir):
                    for f in glob.glob(os.path.join(layer_dir, "*.md")):
                        try:
                            os.remove(f)
                        except OSError:
                            pass
            for f in (
                "personality.json",
                "session.json",
                "index.json",
                "embeddings.json",
                "curator.log",
                "ocean.json",
                "lambda.json",
                "conversation_count.json",
            ):
                p = os.path.join(memory_dir, f)
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

        memory_retrieval.reset_cache()

        functions_dir = os.path.join(root, "brain", "functions")
        if os.path.exists(functions_dir):
            for f in glob.glob(os.path.join(functions_dir, "*.py")):
                os.remove(f)
        brain_file = os.path.join(root, "brain", "brain.py")
        backup_dir = os.path.join(root, "brain", "backup")
        backups = sorted(glob.glob(os.path.join(backup_dir, "brain_*.py")))
        if backups:
            shutil.copy2(backups[-1], brain_file)


COMMANDS = {
    "/clear": "Clears conversation context",
    "/reset": "Factory reset",
    "/help": "Shows available commands",
    "/memory": "List memory entries or manage memory",
    "/memory search <query>": "Search memory",
    "/memory add <layer> <content>": "Add to memory (core/semantic/episodic/procedural)",
    "/memory delete <layer> <filename>": "Delete memory entry",
    "/memory personality": "Show Big Five personality + λ momentum",
    "/memory session": "Show active session",
    "/memory end-session": "Close active session and trigger curation",
    "/status": "Show agent status and memory overview",
    "/permission": "List permission policies",
    "/permission <type> <policy>": "Set permission policy (always_allow/ask/always_deny)",
}


def run() -> None:
    app = CellApp()
    app.run()
