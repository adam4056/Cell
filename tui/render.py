"""Minimal TUI rendering — ANSI codes, no flicker, no engine."""

import os
import shutil
import sys
import threading

_render_lock = threading.Lock()

_GOTO = "\033[{};{}H"
_CLEAR_SCREEN = "\033[2J\033[H"
_CLEAR_LINE = "\033[2K"
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_WHITE = "\033[37m"
_GREEN = "\033[32m"


def _setup_console():
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), 7)


_setup_console()


def _goto(y, x):
    return _GOTO.format(y, x)


def _term_size():
    s = shutil.get_terminal_size()
    return s.lines, s.columns


def draw_screen(messages, input_buffer, attached_file):
    with _render_lock:
        height, width = _term_size()
        log_height = height - 2

        buf = [_CLEAR_SCREEN]

        lines = []
        for role, content in messages:
            for line in content.split("\n"):
                while line:
                    chunk = line[:width]
                    line = line[width:]
                    lines.append((role, chunk))

        visible = lines[-log_height:] if len(lines) > log_height else lines

        y = 1
        for role, text in visible:
            buf.append(_goto(y, 1))
            if role == "user":
                buf.append(f"{_BOLD}{_WHITE}>{_RESET} {text}")
            elif role == "agent":
                buf.append(f"{_BOLD}{_GREEN}<{_RESET} {text}")
            elif role == "system":
                buf.append(f"{_DIM}  {text}{_RESET}")
            y += 1

        for row in range(y, log_height + 1):
            buf.append(_goto(row, 1) + _CLEAR_LINE)

        buf.append(_goto(height - 1, 1) + _CLEAR_LINE + "─" * (width - 1))

        buf.append(_goto(height, 1) + _CLEAR_LINE)
        if attached_file:
            buf.append(f"{_DIM} {os.path.basename(attached_file)} ")
        buf.append(f"> {input_buffer}")

        sys.stdout.write("".join(buf))
        sys.stdout.flush()


def draw_input(input_buffer, attached_file):
    with _render_lock:
        height, width = _term_size()

        buf = []
        buf.append(_goto(height - 1, 1) + _CLEAR_LINE + "─" * (width - 1))

        buf.append(_goto(height, 1) + _CLEAR_LINE)
        if attached_file:
            buf.append(f"{_DIM} {os.path.basename(attached_file)} ")
        buf.append(f"> {input_buffer}")

        sys.stdout.write("".join(buf))
        sys.stdout.flush()


def draw_dialog(label, prompt, existing, secret, input_buffer):
    height, width = _term_size()
    dialog_w = min(60, width - 4)

    wrapped = _wrap_text(prompt, dialog_w - 5)
    prompt_lines = len(wrapped)
    dialog_h = 10 + prompt_lines
    start_y = max(1, (height - dialog_h) // 2)
    start_x = max(1, (width - dialog_w) // 2)

    def _box(s):
        return f"│ {s:<{dialog_w - 4}} │"

    buf = [_CLEAR_SCREEN]
    row = start_y

    buf.append(_goto(row, start_x) + f"{_BOLD}┌{'─' * (dialog_w - 2)}┐{_RESET}")
    row += 1
    buf.append(_goto(row, start_x) + _box(f"{_BOLD}{label}{_RESET}"))
    row += 1
    buf.append(_goto(row, start_x) + _box("─" * (dialog_w - 4)))
    row += 1

    for line in wrapped:
        buf.append(_goto(row, start_x) + _box(f"{line}"))
        row += 1

    buf.append(_goto(row, start_x) + _box(""))
    row += 1
    if existing:
        buf.append(
            _goto(row, start_x) + _box(f"{_DIM}Current: {existing[:30]}...{_RESET}")
        )
        row += 1

    masked = "*" * len(input_buffer) if secret else input_buffer
    buf.append(_goto(row, start_x) + _box(f"> {masked}"))
    row += 1
    buf.append(_goto(row, start_x) + _box(""))
    row += 1
    buf.append(
        _goto(row, start_x) + _box(f"{_DIM}Enter = save     Esc = cancel{_RESET}")
    )
    row += 1
    buf.append(_goto(row, start_x) + f"└{'─' * (dialog_w - 2)}┘")

    sys.stdout.write("".join(buf))
    sys.stdout.flush()


def _wrap_text(text, width):
    words = text.split()
    lines = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 <= width:
            current = (current + " " + w) if current else w
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines or [""]
