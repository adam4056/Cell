"""Factory function: browser — full browser automation via Playwright.

Actions: navigate, click, type, screenshot, extract, wait, scroll, press_key, close.
The browser persists across calls — navigate once, then click/type/extract as needed.
Closes automatically after 5 minutes idle.
"""
import json

SPEC = {
    "description": "Full web browser automation via Playwright (auto-installed if missing). Actions: navigate(url) — open a page, click(selector) — click element, type(selector, text) — fill input, screenshot() — capture visible page as base64, extract(selector?) — get text from element or whole page, wait(selector) — wait for element, scroll(down|up|bottom|top), press_key(key), close() — end session. Use this for: logins, forms, JS-heavy sites, interactive workflows. The browser stays open between calls.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Browser action: 'navigate', 'click', 'type', 'screenshot', 'extract', 'wait', 'scroll', 'press_key', 'close'",
                "enum": ["navigate", "click", "type", "screenshot", "extract", "wait", "scroll", "press_key", "close"],
            },
            "url": {"type": "string", "description": "URL for navigate action"},
            "selector": {"type": "string", "description": "CSS selector for click/type/extract/wait"},
            "text": {"type": "string", "description": "Text to type (for type action)"},
            "direction": {"type": "string", "description": "Scroll direction: 'down', 'up', 'bottom', 'top' (default 'down')"},
            "amount": {"type": "integer", "description": "Scroll amount in pixels (default 500)"},
            "key": {"type": "string", "description": "Key to press (e.g. 'Enter', 'Escape', 'Tab')"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
        },
        "required": ["action"],
    },
}


def run(**kwargs):
    from core.browser_actions import (
        browser_navigate, browser_click, browser_type, browser_screenshot,
        browser_extract, browser_wait, browser_scroll, browser_press_key,
        browser_close,
    )
    action = kwargs["action"]

    if action == "navigate":
        result = browser_navigate(kwargs.get("url", ""), kwargs.get("timeout", 30))
    elif action == "click":
        result = browser_click(kwargs.get("selector", ""), kwargs.get("timeout", 10))
    elif action == "type":
        result = browser_type(kwargs.get("selector", ""), kwargs.get("text", ""), kwargs.get("timeout", 10))
    elif action == "screenshot":
        result = browser_screenshot()
    elif action == "extract":
        result = browser_extract(kwargs.get("selector"))
    elif action == "wait":
        result = browser_wait(kwargs.get("selector", ""), kwargs.get("timeout", 15))
    elif action == "scroll":
        result = browser_scroll(kwargs.get("direction", "down"), kwargs.get("amount", 500))
    elif action == "press_key":
        result = browser_press_key(kwargs.get("key", ""))
    elif action == "close":
        result = browser_close()
    else:
        result = {"success": False, "error": f"Unknown action: {action}"}

    return json.dumps(result, ensure_ascii=False)
