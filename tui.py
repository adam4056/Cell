import os
import sys
import glob
import shutil
import threading
import time
import yaml

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical, Horizontal
from textual.reactive import reactive
from textual.widgets import Input, Static, Label
from textual import work
from rich.markdown import Markdown
from rich.text import Text

ROOT = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(ROOT, "config.yaml")

COMMANDS = {
    "/clear": "Clears conversation context",
    "/reset": "Factory reset",
    "/help":  "Shows available commands",
}


def _load_ambient() -> int:
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return int(yaml.safe_load(f).get("ambient_interval_seconds", 0) or 0)
    return 0


def _factory_reset() -> None:
    for f in ("context.json", "memory.json", "schedule.json", "summary.json"):
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            os.remove(p)
    functions_dir = os.path.join(ROOT, "brain", "functions")
    if os.path.exists(functions_dir):
        for f in glob.glob(os.path.join(functions_dir, "*.py")):
            os.remove(f)
    brain_file = os.path.join(ROOT, "brain", "brain.py")
    backup_dir = os.path.join(ROOT, "brain", "backup")
    backups = sorted(glob.glob(os.path.join(backup_dir, "brain_*.py")))
    if backups:
        shutil.copy2(backups[-1], brain_file)


class MessageWidget(Static):
    """Single chat message bubble."""

    DEFAULT_CSS = """
    MessageWidget {
        width: 100%;
        padding: 1 2;
        margin-bottom: 0;
    }
    MessageWidget.user {
        background: #1e2030;
        border-left: thick #4fc3f7;
        color: #cdd6f4;
    }
    MessageWidget.agent {
        background: #181825;
        border-left: thick #a6e3a1;
        color: #cdd6f4;
    }
    MessageWidget.system {
        background: #11111b;
        border-left: thick #f38ba8;
        color: #6c7086;
    }
    MessageWidget.thinking {
        background: #11111b;
        border-left: thick #fab387;
        color: #6c7086;
    }
    """

    def __init__(self, role: str, content: str) -> None:
        super().__init__()
        self.role = role
        self._content = content
        self.add_class(role)

    def compose(self) -> ComposeResult:
        labels = {"user": "You", "agent": "Cell-2", "system": "System", "thinking": "..."}
        label = labels.get(self.role, self.role)
        color = {"user": "bold #4fc3f7", "agent": "bold #a6e3a1",
                 "system": "bold #f38ba8", "thinking": "bold #fab387"}.get(self.role, "bold white")
        yield Label(f"[{color}]{label}[/]")
        if self.role == "agent":
            yield Static(Markdown(self._content))
        else:
            yield Static(self._content)

    def update_content(self, content: str) -> None:
        self._content = content
        try:
            body = self.query("Static").last()
            if self.role == "agent":
                body.update(Markdown(content))
            else:
                body.update(content)
        except Exception:
            pass


class StatusBar(Static):
    DEFAULT_CSS = """
    StatusBar {
        height: 2;
        background: #181825;
        color: #6c7086;
        padding: 0 2;
        border-top: solid #313244;
    }
    StatusBar .status-ok { color: #a6e3a1; }
    StatusBar .status-busy { color: #fab387; }
    """

    status: reactive[str] = reactive("idle")
    model: reactive[str] = reactive("deepseek")
    tokens: reactive[str] = reactive("—")

    def render(self) -> Text:
        status_style = "status-ok" if self.status == "idle" else "status-busy"
        t = Text()
        t.append("connected", style="bold #a6e3a1")
        t.append(" | ")
        t.append(self.status, style="bold #fab387" if self.status != "idle" else "bold #a6e3a1")
        t.append("\n")
        t.append("Cell-2 agent", style="#4fc3f7")
        t.append(f" | {self.model} | tokens: {self.tokens}", style="#6c7086")
        return t


class Cell2TUI(App):
    CSS = """
    Screen {
        background: #11111b;
    }
    #header {
        height: 2;
        background: #181825;
        color: #a6e3a1;
        padding: 0 2;
        border-bottom: solid #313244;
    }
    #chat {
        height: 1fr;
        overflow-y: auto;
    }
    #input-bar {
        height: auto;
        background: #1e2030;
        padding: 0 2;
        border-top: solid #313244;
    }
    #input-bar Input {
        background: #1e2030;
        border: none;
        color: #cdd6f4;
    }
    #input-bar Input:focus {
        border: none;
        outline: none;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "clear_chat", "Clear"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._model_name = "deepseek"
        self._thinking_widget: MessageWidget | None = None

    def compose(self) -> ComposeResult:
        yield Static("[bold #a6e3a1]Cell-2 Agent[/]  [#6c7086]— type /help for commands, Ctrl+C to quit[/]", id="header")
        with ScrollableContainer(id="chat"):
            pass
        with Vertical(id="input-bar"):
            yield Input(placeholder="> enter message or command...")
        yield StatusBar()

    def on_mount(self) -> None:
        from core.core import start_scheduler
        from core import inbox
        ambient = _load_ambient()
        start_scheduler(ambient_interval=ambient)
        self._inbox = inbox
        self.set_interval(1.5, self._check_inbox)
        self.query_one(Input).focus()

    def _check_inbox(self) -> None:
        msgs = self._inbox.drain()
        for m in msgs:
            self._add_message("system", m)

    def _add_message(self, role: str, content: str) -> MessageWidget:
        widget = MessageWidget(role, content)
        chat = self.query_one("#chat", ScrollableContainer)
        self.app.call_from_thread(chat.mount, widget)
        self.app.call_from_thread(chat.scroll_end, animate=False)
        return widget

    def _set_status(self, status: str) -> None:
        self.app.call_from_thread(
            setattr, self.query_one(StatusBar), "status", status
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text.startswith("/"):
            self._handle_command(text)
            return
        chat = self.query_one("#chat", ScrollableContainer)
        chat.mount(MessageWidget("user", text))
        chat.scroll_end(animate=False)
        self._run_brain(text)

    def _handle_command(self, cmd: str) -> None:
        if cmd == "/help":
            lines = "\n".join(f"{k}  — {v}" for k, v in COMMANDS.items())
            chat = self.query_one("#chat", ScrollableContainer)
            chat.mount(MessageWidget("system", lines))
            chat.scroll_end(animate=False)
        elif cmd == "/clear":
            ctx = os.path.join(ROOT, "context.json")
            if os.path.exists(ctx):
                os.remove(ctx)
            chat = self.query_one("#chat", ScrollableContainer)
            chat.mount(MessageWidget("system", "Context cleared."))
            chat.scroll_end(animate=False)
        elif cmd == "/reset":
            _factory_reset()
            chat = self.query_one("#chat", ScrollableContainer)
            chat.mount(MessageWidget("system", "Factory reset complete."))
            chat.scroll_end(animate=False)
        else:
            chat = self.query_one("#chat", ScrollableContainer)
            chat.mount(MessageWidget("system", f"Unknown command: {cmd}. Type /help."))
            chat.scroll_end(animate=False)

    @work(thread=True)
    def _run_brain(self, text: str) -> None:
        from core.core import process

        thinking = MessageWidget("thinking", "thinking...")
        chat = self.query_one("#chat", ScrollableContainer)
        self.app.call_from_thread(chat.mount, thinking)
        self.app.call_from_thread(chat.scroll_end, animate=False)

        status_bar = self.query_one(StatusBar)
        self.app.call_from_thread(setattr, status_bar, "status", "thinking")

        brain_events: list[str] = []

        def on_event(msg: str) -> None:
            brain_events.append(msg)
            self.app.call_from_thread(
                thinking.update_content,
                "\n".join(brain_events[-5:])
            )

        response = process(text, on_event=on_event)

        self.app.call_from_thread(thinking.remove)
        chat2 = self.query_one("#chat", ScrollableContainer)
        self.app.call_from_thread(chat2.mount, MessageWidget("agent", response))
        self.app.call_from_thread(chat2.scroll_end, animate=False)
        self.app.call_from_thread(setattr, status_bar, "status", "idle")

    def action_clear_chat(self) -> None:
        chat = self.query_one("#chat", ScrollableContainer)
        for w in chat.query(MessageWidget):
            w.remove()

    def action_quit(self) -> None:
        self.exit()


if __name__ == "__main__":
    Cell2TUI().run()
