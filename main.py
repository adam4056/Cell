"""Cell entrypoint.

  python main.py            TUI mode (terminal interface)
  python main.py --headless  Headless mode (Telegram bot only)
  python main.py --tg        Same as --headless
"""

import sys


def run_tui():
    from tui.app import run
    run()


def run_headless():
    import os
    import shutil
    import time
    from core.core import start_scheduler
    from core.telegram_bot import start as start_tg

    if not os.path.exists(os.path.join(os.path.dirname(__file__), "core", "brain.py")):
        factory = os.path.join(os.path.dirname(__file__), "core", "brain_factory.py")
        brain = os.path.join(os.path.dirname(__file__), "core", "brain.py")
        if os.path.exists(factory):
            shutil.copy2(factory, brain)

    start_scheduler()
    started = start_tg()

    if not started:
        print("Error: telegram_bot_token not set in config.yaml")
        sys.exit(1)

    print("Cell running in headless mode (Telegram bot only). Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    print("\nGoodbye.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--headless" in args or "--tg" in args:
        run_headless()
    else:
        run_tui()
