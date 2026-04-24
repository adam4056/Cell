import os
import sys
import shutil
import glob
import threading
import time
import yaml
from rich.console import Console
from rich.markdown import Markdown

_console = Console()
from core.core import process, start_scheduler
from core import context_store, inbox

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

ROOT = os.path.dirname(os.path.abspath(__file__))

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
DIM    = "\033[2m"
MAGENTA = "\033[95m"

MONITOR = "--monitor" in sys.argv

COMMANDS = {
    "/clear": "Clears conversation context",
    "/reset": "Factory reset — clears context, memory, functions, restores brain.py",
    "/help":  "Shows available commands",
}

_stdout_lock = threading.Lock()


def _safe_print(text: str) -> None:
    with _stdout_lock:
        sys.stdout.write(text)
        sys.stdout.flush()


def _header():
    _safe_print(f"\n{BOLD}{CYAN}╔══════════════════════════════╗{RESET}\n")
    _safe_print(f"{BOLD}{CYAN}║        Cell-2  Agent         ║{RESET}\n")
    if MONITOR:
        _safe_print(f"{BOLD}{CYAN}║     [monitor mode active]    ║{RESET}\n")
    _safe_print(f"{BOLD}{CYAN}╚══════════════════════════════╝{RESET}\n\n")


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
    factory_file = os.path.join(ROOT, "brain", "brain_factory.py")
    if os.path.exists(factory_file):
        shutil.copy2(factory_file, brain_file)
        print(f"{YELLOW}brain.py restored from factory defaults (brain_factory.py){RESET}")
    else:
        print(f"{RED}brain_factory.py missing — factory restore of brain.py skipped.{RESET}")


def _handle_command(cmd: str) -> bool:
    if cmd == "/clear":
        ctx_file = os.path.join(ROOT, "context.json")
        if os.path.exists(ctx_file):
            os.remove(ctx_file)
        print(f"{YELLOW}Context cleared.{RESET}\n")
        return True
    if cmd == "/reset":
        print(f"{RED}Factory reset will delete context, memory, plans and all self-generated functions.{RESET}")
        try:
            confirm = input(f"{BOLD}Really continue? [yes/no]: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return True
        if confirm == "yes":
            _factory_reset()
            print(f"{YELLOW}Reset complete.{RESET}\n")
        else:
            print(f"{DIM}Cancelled.{RESET}\n")
        return True
    if cmd == "/help":
        print(f"{BOLD}Available commands:{RESET}")
        for name, desc in COMMANDS.items():
            print(f"  {CYAN}{name}{RESET}  {DIM}{desc}{RESET}")
        print()
        return True
    print(f"{RED}Unknown command. Type /help.{RESET}\n")
    return True


def _inbox_printer(interval_s: float = 1.5) -> None:
    while True:
        msgs = inbox.drain()
        if msgs:
            buf = ["\n"]
            for m in msgs:
                for line in m.splitlines() or [""]:
                    buf.append(f"{MAGENTA}📬 {line}{RESET}\n")
            buf.append(f"{BOLD}{CYAN}You:{RESET} ")
            _safe_print("".join(buf))
        time.sleep(interval_s)


def main():
    _header()
    ambient = 0
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            ambient = int(yaml.safe_load(f).get("ambient_interval_seconds", 0) or 0)
    start_scheduler(ambient_interval=ambient)
    threading.Thread(target=_inbox_printer, daemon=True).start()
    if MONITOR and ambient > 0:
        print(f"{DIM}  ambient loop: {ambient}s{RESET}")
    print(f"{DIM}Type /help for a list of commands. Ctrl+C to quit.{RESET}\n")

    while True:
        try:
            user_input = input(f"{BOLD}{CYAN}You:{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Exiting.{RESET}")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            _handle_command(user_input)
            continue

        brain_active = [False]

        def on_event(msg):
            is_timing = msg.startswith("⏱")
            if is_timing and not MONITOR:
                return
            with _stdout_lock:
                if not brain_active[0]:
                    sys.stdout.write(f"\n{DIM}┌─ Brain ──────────────────────────────┐{RESET}\n")
                    brain_active[0] = True
                sys.stdout.write(f"{DIM}│ {msg}{RESET}\n")
                sys.stdout.flush()

        t_start = time.perf_counter()
        response = process(user_input, on_event=on_event)
        t_total = time.perf_counter() - t_start

        if brain_active[0]:
            _safe_print(f"{DIM}└──────────────────────────────────────┘{RESET}\n")

        if MONITOR:
            _safe_print(f"{DIM}  ⏱ total: {t_total:.2f}s{RESET}\n")

        if response.startswith("[SYSTEM ERROR]"):
            with _stdout_lock:
                print(f"\n{RED}╔─ Error ──────────────────────────────╗{RESET}")
                for line in response.splitlines():
                    print(f"{RED}│{RESET} {line}")
                print(f"{RED}╚──────────────────────────────────────╝{RESET}\n")
        else:
            with _stdout_lock:
                print(f"\n{BOLD}{GREEN}Cell-2:{RESET}\n")
                _console.print(Markdown(response))
                print()


if __name__ == "__main__":
    main()
