"""Cell Browser — Lightweight web browsing for the agent.

Uses requests + BeautifulSoup for simple sites.
For JS-heavy sites, falls back to playwright (if installed).
"""

import re
from typing import Any

try:
    import requests
    from bs4 import BeautifulSoup

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from playwright.sync_api import sync_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


def _clean_text(text: str) -> str:
    """Remove extra whitespace."""
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def fetch_url(url: str, timeout: int = 30) -> dict[str, Any]:
    """Fetch and extract text from URL using requests."""
    if not HAS_REQUESTS:
        return {
            "success": False,
            "error": "requests + beautifulsoup4 not installed. Install with: pip install requests beautifulsoup4",
            "text": "",
            "title": "",
        }

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(
            url, headers=headers, timeout=timeout, allow_redirects=True
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        title = soup.find("title")
        title_text = title.get_text().strip() if title else ""

        # Try to find main content
        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_=re.compile("content|main|article"))
        )
        if main:
            text = main.get_text()
        else:
            text = soup.get_text()

        cleaned = _clean_text(text)
        # Limit to reasonable size
        if len(cleaned) > 10000:
            cleaned = cleaned[:10000] + "\n\n[Content truncated...]"

        return {
            "success": True,
            "title": title_text,
            "text": cleaned,
            "url": response.url,
            "status_code": response.status_code,
        }

    except Exception as e:
        return {"success": False, "error": str(e), "text": "", "title": ""}


def fetch_with_browser(
    url: str, timeout: int = 30, wait_for: str | None = None
) -> dict[str, Any]:
    """Fetch URL using headless browser (playwright)."""
    if not HAS_PLAYWRIGHT:
        return {
            "success": False,
            "error": "playwright not installed. Install with: pip install playwright && playwright install chromium",
            "text": "",
            "title": "",
        }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=timeout * 1000, wait_until="networkidle")

            if wait_for:
                page.wait_for_selector(wait_for, timeout=5000)

            title = page.title()
            text = page.inner_text("body")
            cleaned = _clean_text(text)

            if len(cleaned) > 10000:
                cleaned = cleaned[:10000] + "\n\n[Content truncated...]"

            browser.close()

            return {
                "success": True,
                "title": title,
                "text": cleaned,
                "url": url,
            }

    except Exception as e:
        return {"success": False, "error": str(e), "text": "", "title": ""}


def search_web(query: str, num_results: int = 5) -> dict[str, Any]:
    """Simple web search via DuckDuckGo HTML."""
    if not HAS_REQUESTS:
        return {"success": False, "error": "requests not installed", "results": []}

    try:
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for result in soup.select(".result")[:num_results]:
            title_el = result.select_one(".result__a")
            snippet_el = result.select_one(".result__snippet")
            url_el = result.select_one(".result__url")

            if title_el:
                results.append(
                    {
                        "title": title_el.get_text(strip=True),
                        "url": url_el.get_text(strip=True) if url_el else "",
                        "snippet": snippet_el.get_text(strip=True)
                        if snippet_el
                        else "",
                    }
                )

        return {"success": True, "results": results}

    except Exception as e:
        return {"success": False, "error": str(e), "results": []}
