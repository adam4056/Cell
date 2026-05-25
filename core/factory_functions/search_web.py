"""System function: search_web — search DuckDuckGo for web results."""
import json

SPEC = {
    "description": "Search the web using DuckDuckGo. Returns a list of results with title, URL, and snippet. Use this for finding information, current events, or anything you need to look up online.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default 5, max 10)",
            },
        },
        "required": ["query"],
    },
}


def run(**kwargs):
    from core.browser import search_web

    result = search_web(kwargs["query"], kwargs.get("num_results", 5))
    return json.dumps(result, ensure_ascii=False)
