"""Cell Browser — Lightweight web browsing for the agent.

Uses requests + BeautifulSoup for simple sites.
Multi-engine search with fallback chain: Google → DuckDuckGo.
For JS-heavy sites, falls back to playwright (if installed).
"""

import random
import re
from typing import Any
from urllib.parse import quote_plus

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

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]


def _random_ua() -> str:
    return random.choice(_USER_AGENTS)


def _clean_text(text: str) -> str:
    """Remove extra whitespace."""
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _default_headers() -> dict:
    return {"User-Agent": _random_ua()}


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
        response = requests.get(
            url, headers=_default_headers(), timeout=timeout, allow_redirects=True
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        title = soup.find("title")
        title_text = title.get_text().strip() if title else ""

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


def _search_google(query: str, num_results: int = 5) -> dict[str, Any]:
    """Search Google via HTML scraping. Returns results or error dict."""
    try:
        url = f"https://www.google.com/search?q={quote_plus(query)}&hl=en"
        response = requests.get(url, headers=_default_headers(), timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for g in soup.select(".g")[:num_results]:
            title_el = g.select_one("h3")
            link_el = g.select_one("a")
            snippet_el = g.select_one(".VwiC3b") or g.select_one("span.st")

            title = title_el.get_text(strip=True) if title_el else ""
            url = link_el.get("href") if link_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            if title or url:
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "source": "google",
                })

        if not results:
            # Google may have returned a CAPTCHA / block page
            return {"success": False, "error": "Google returned no results (possible CAPTCHA)", "results": []}

        return {"success": True, "results": results}

    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return {"success": False, "error": "Google rate-limited (429)", "results": []}
        return {"success": False, "error": f"Google HTTP {e.response.status_code if e.response else 'error'}", "results": []}
    except Exception as e:
        return {"success": False, "error": str(e), "results": []}


def _search_ddg(query: str, num_results: int = 5) -> dict[str, Any]:
    """Search DuckDuckGo HTML (fallback)."""
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        response = requests.get(url, headers=_default_headers(), timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for result in soup.select(".result")[:num_results]:
            title_el = result.select_one(".result__a")
            snippet_el = result.select_one(".result__snippet")
            url_el = result.select_one(".result__url")

            title = title_el.get_text(strip=True) if title_el else ""
            url = url_el.get_text(strip=True) if url_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            if title or url:
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "source": "duckduckgo",
                })

        return {"success": True, "results": results} if results else {"success": False, "error": "DuckDuckGo returned no results", "results": []}

    except Exception as e:
        return {"success": False, "error": str(e), "results": []}


def search_web(query: str, num_results: int = 5) -> dict[str, Any]:
    """Multi-engine web search. Tries Google first, falls back to DuckDuckGo."""
    if not HAS_REQUESTS:
        return {"success": False, "error": "requests not installed", "results": []}

    google = _search_google(query, num_results)
    if google["success"] and google["results"]:
        return google

    ddg = _search_ddg(query, num_results)
    if ddg["success"]:
        ddg["fallback_used"] = "google_failed"
        if google.get("error"):
            ddg["google_error"] = google["error"]
        return ddg

    return {"success": False, "error": f"All search engines failed. Google: {google.get('error', '?')} | DuckDuckGo: {ddg.get('error', '?')}", "results": []}
