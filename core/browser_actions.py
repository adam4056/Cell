"""Browser automation — full Playwright-based browser with clicks, typing, screenshots.

The agent gets a stateful browser instance. Actions: navigate, click, type,
screenshot, extract, wait, scroll, press_key. The browser auto-installs Playwright
if missing.
"""

import base64
import json
import os
import sys
import subprocess
import time
import threading

_HAS_PLAYWRIGHT = False
_BROWSER = None
_PAGE = None
_LOCK = threading.Lock()


def _ensure_playwright():
    global _HAS_PLAYWRIGHT
    if _HAS_PLAYWRIGHT:
        return True
    try:
        from playwright.sync_api import sync_playwright
        _HAS_PLAYWRIGHT = True
        return True
    except ImportError:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "playwright"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            subprocess.check_call(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            from playwright.sync_api import sync_playwright
            _HAS_PLAYWRIGHT = True
            return True
        except Exception:
            return False


def _get_page():
    global _BROWSER, _PAGE
    from playwright.sync_api import sync_playwright
    if _BROWSER is None:
        _BROWSER = sync_playwright().start()
    if _PAGE is None or _PAGE.is_closed():
        browser = _BROWSER.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        )
        _PAGE = context.new_page()
    return _PAGE


def browser_navigate(url: str, timeout: int = 30) -> dict:
    if not _ensure_playwright():
        return {"success": False, "error": "Playwright install failed. Run: pip install playwright && playwright install chromium"}
    with _LOCK:
        try:
            page = _get_page()
            page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
            title = page.title()
            body_text = page.inner_text("body")
            if len(body_text) > 8000:
                body_text = body_text[:8000] + "\n...[truncated]"
            return {
                "success": True,
                "url": page.url,
                "title": title,
                "text": body_text,
                "actions_available": True,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


def browser_click(selector: str, timeout: int = 10) -> dict:
    if not _ensure_playwright():
        return {"success": False, "error": "Playwright not available"}
    with _LOCK:
        try:
            page = _get_page()
            page.wait_for_selector(selector, timeout=timeout * 1000)
            page.click(selector)
            page.wait_for_load_state("networkidle")
            return {"success": True, "action": "click", "selector": selector, "url": page.url, "title": page.title()}
        except Exception as e:
            return {"success": False, "error": str(e)}


def browser_type(selector: str, text: str, timeout: int = 10) -> dict:
    if not _ensure_playwright():
        return {"success": False, "error": "Playwright not available"}
    with _LOCK:
        try:
            page = _get_page()
            page.wait_for_selector(selector, timeout=timeout * 1000)
            page.fill(selector, text)
            return {"success": True, "action": "type", "selector": selector}
        except Exception as e:
            return {"success": False, "error": str(e)}


def browser_screenshot() -> dict:
    if not _ensure_playwright():
        return {"success": False, "error": "Playwright not available"}
    with _LOCK:
        try:
            page = _get_page()
            screenshot_bytes = page.screenshot(full_page=False)
            b64 = base64.b64encode(screenshot_bytes).decode("ascii")
            return {"success": True, "image_base64": b64, "mime_type": "image/png"}
        except Exception as e:
            return {"success": False, "error": str(e)}


def browser_extract(selector: str | None = None) -> dict:
    if not _ensure_playwright():
        return {"success": False, "error": "Playwright not available"}
    with _LOCK:
        try:
            page = _get_page()
            if selector:
                el = page.query_selector(selector)
                if el is None:
                    return {"success": False, "error": f"Element not found: {selector}"}
                text = el.inner_text()
            else:
                text = page.inner_text("body")
            if len(text) > 8000:
                text = text[:8000] + "\n...[truncated]"
            return {"success": True, "text": text, "url": page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}


def browser_wait(selector: str, timeout: int = 15) -> dict:
    if not _ensure_playwright():
        return {"success": False, "error": "Playwright not available"}
    with _LOCK:
        try:
            page = _get_page()
            page.wait_for_selector(selector, timeout=timeout * 1000)
            return {"success": True, "selector": selector, "url": page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}


def browser_scroll(direction: str = "down", amount: int = 500) -> dict:
    if not _ensure_playwright():
        return {"success": False, "error": "Playwright not available"}
    with _LOCK:
        try:
            page = _get_page()
            if direction == "down":
                page.evaluate(f"window.scrollBy(0, {amount})")
            elif direction == "up":
                page.evaluate(f"window.scrollBy(0, -{amount})")
            elif direction == "bottom":
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif direction == "top":
                page.evaluate("window.scrollTo(0, 0)")
            return {"success": True, "action": f"scroll {direction}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


def browser_press_key(key: str) -> dict:
    if not _ensure_playwright():
        return {"success": False, "error": "Playwright not available"}
    with _LOCK:
        try:
            page = _get_page()
            page.keyboard.press(key)
            return {"success": True, "action": f"press {key}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


def browser_close() -> dict:
    global _BROWSER, _PAGE
    with _LOCK:
        try:
            if _PAGE:
                _PAGE.close()
                _PAGE = None
            if _BROWSER:
                _BROWSER.stop()
                _BROWSER = None
            return {"success": True, "message": "Browser closed"}
        except Exception as e:
            return {"success": False, "error": str(e)}
