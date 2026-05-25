"""Factory function: Brave Search.

Ships with the project, lives in `brain/factory_functions/`, NOT in
`brain/functions/` — so factory_reset() doesn't wipe it and self_improve
doesn't accidentally rewrite it.

Reads `brave_search_api_key` from the project's config.yaml. The brain
subprocess has filesystem access to read it directly.
"""

import os
import yaml
import requests

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


def _load_key() -> str:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return (cfg.get("brave_search_api_key") or "").strip()
    except Exception:
        return ""


def run(**kwargs):
    query = (kwargs.get("query") or "").strip()
    if not query:
        return {"error": "query is required"}

    try:
        count = int(kwargs.get("count", 5))
    except (TypeError, ValueError):
        count = 5
    count = max(1, min(20, count))

    key = _load_key()
    if not key:
        return {"error": "brave_search_api_key is empty in config.yaml. Get one at https://brave.com/search/api/"}

    try:
        r = requests.get(
            ENDPOINT,
            headers={
                "X-Subscription-Token": key,
                "Accept": "application/json",
            },
            params={"q": query, "count": count},
            timeout=20,
        )
    except Exception as e:
        return {"error": f"network error: {e}"}

    if not r.ok:
        return {"error": f"{r.status_code} {r.reason}: {(r.text or '')[:300]}"}

    data = r.json()
    results = []
    for item in (data.get("web") or {}).get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "description": item.get("description", ""),
        })

    return {"query": query, "count": len(results), "results": results}


SPEC = {
    "description": "Search the web via Brave Search and return top results (title, URL, snippet). Use for current events, factual lookups, finding URLs.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query in natural language, like a Google search.",
            },
            "count": {
                "type": "integer",
                "description": "Number of results to return (1-20). Default 5.",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}
