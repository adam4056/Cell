"""Cell web entry point — `python cell2_web.py` opens the dashboard."""

import sys
import threading
import time
import webbrowser

from core.web_server import serve

HOST = "127.0.0.1"
PORT = 8765


def _open_browser():
    time.sleep(1.0)
    try:
        webbrowser.open(f"http://{HOST}:{PORT}")
    except Exception:
        pass


if __name__ == "__main__":
    if "--no-browser" not in sys.argv:
        threading.Thread(target=_open_browser, daemon=True).start()
    print(f"Cell web — http://{HOST}:{PORT}")
    serve(host=HOST, port=PORT)
