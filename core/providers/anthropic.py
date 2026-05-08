import json
import requests

from core.providers.base import BaseProvider, ProviderError

# Anthropic doesn't support native tool calling in the same way as OpenAI.
# We normalize their format into OpenAI-compatible tool_calls.


class AnthropicProvider(BaseProvider):
    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.url = "https://api.anthropic.com/v1/messages"
        self.api_version = config.get("api_version", "2023-06-01")

    def _map_tools(self, tools: list[dict]) -> list[dict]:
        result = []
        for t in tools:
            result.append(
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"].get(
                        "parameters", {"type": "object", "properties": {}}
                    ),
                }
            )
        return result

    def _map_messages(self, messages: list[dict]) -> tuple[list[dict], str | None]:
        system_msg = None
        mapped = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
                continue
            mapped.append({"role": m["role"], "content": m["content"]})
        return mapped, system_msg

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        timeout: int = 120,
    ) -> dict:
        request_model = model or self.model
        mapped_messages, system_msg = self._map_messages(messages)
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": request_model,
            "max_tokens": 8192,
            "messages": mapped_messages,
        }
        if system_msg:
            payload["system"] = system_msg
        if tools:
            payload["tools"] = self._map_tools(tools)

        response = requests.post(
            self.url, headers=headers, json=payload, timeout=timeout
        )
        if not response.ok:
            body = (response.text or "").strip()[:2000]
            raise ProviderError(f"{response.status_code} {response.reason}: {body}")

        data = response.json()
        self._last_usage = data.get("usage", {})
        content_blocks = data.get("content", [])
        text_parts = []
        tool_calls = []
        for block in content_blocks:
            if block["type"] == "text":
                text_parts.append(block["text"])
            elif block["type"] == "tool_use":
                tool_calls.append(
                    {
                        "id": block.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": json.dumps(
                                block.get("input", {}), ensure_ascii=False
                            ),
                        },
                    }
                )
        message = {
            "role": "assistant",
            "content": "\n".join(text_parts) if text_parts else None,
        }
        if tool_calls:
            message["tool_calls"] = tool_calls
        return message
