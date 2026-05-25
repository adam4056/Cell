"""System function: fetch_url — fetch and extract text from any URL."""
import json

SPEC = {
    "description": "Fetch and extract text content from any URL. Returns page title and text. Works with static websites via requests+BeautifulSoup. Use this whenever you need to read a webpage.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full URL including https://",
            },
            "timeout": {
                "type": "integer",
                "description": "Request timeout in seconds (default 30)",
            },
        },
        "required": ["url"],
    },
}


def run(**kwargs):
    from core.browser import fetch_url

    result = fetch_url(kwargs["url"], kwargs.get("timeout", 30))
    return json.dumps(result, ensure_ascii=False)
