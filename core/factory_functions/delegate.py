"""Factory function: delegate — spawn a subagent for parallel work.

The subagent runs in isolation: no conversation history, no memory writes.
Useful for: researching multiple things in parallel, offloading sub-tasks,
preparing data while you work on the main response.
"""
import json

SPEC = {
    "description": "Spawn an isolated subagent to work on a task in parallel. The subagent has the full system prompt but no conversation history. It returns the task result as text. Use this for parallel workstreams — spawn multiple delegates at once for independent sub-tasks. The subagent runs in a thread and joins with a timeout.",
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Task description the subagent should complete. Be specific — the subagent sees only this and the system prompt. Example: 'Search for the current BTC price and the top 3 news headlines about crypto. Return a bullet list.'",
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum seconds to wait for the subagent (default 120)",
            },
        },
        "required": ["task"],
    },
}


def run(**kwargs):
    from core.delegate import delegate_task
    result = delegate_task(kwargs["task"], kwargs.get("timeout", 120))
    return json.dumps(result, ensure_ascii=False)
