import json
import requests

from core.providers.base import BaseProvider, ProviderError


class GeminiProvider(BaseProvider):
    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.api_base = (
            config.get("api_base") or "https://generativelanguage.googleapis.com/v1beta"
        ).rstrip("/")
        self.use_openai_compat = config.get("use_openai_compat", False)
        if self.use_openai_compat:
            self.url = self.api_base + "/openai/chat/completions"
        else:
            self.url_template = self.api_base + "/models/{model}:generateContent"

    def _map_tools(self, tools: list[dict]) -> list[dict]:
        declarations = []
        for t in tools:
            func = t.get("function", {})
            declarations.append(
                {
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "parameters": func.get(
                        "parameters", {"type": "object", "properties": {}}
                    ),
                }
            )
        return [{"function_declarations": declarations}]

    def _map_messages(self, messages: list[dict]) -> tuple[list[dict], str | None]:
        system_msg = None
        mapped = []
        gemini_roles = {"user": "user", "assistant": "model"}
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
                continue
            role = gemini_roles.get(m["role"], "user")
            mapped.append({"role": role, "parts": [{"text": m["content"]}]})
        return mapped, system_msg

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        timeout: int = 120,
    ) -> dict:
        request_model = model or self.model

        if self.use_openai_compat:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload: dict = {"model": request_model, "messages": messages}
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            response = requests.post(
                self.url, headers=headers, json=payload, timeout=timeout
            )
            if not response.ok:
                body = (response.text or "").strip()[:2000]
                raise ProviderError(f"{response.status_code} {response.reason}: {body}")
            data = response.json()
            self._last_usage = data.get("usage", {})
            return data["choices"][0]["message"]

        url = self.url_template.format(model=request_model)
        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}

        mapped_messages, system_msg = self._map_messages(messages)
        payload: dict = {"contents": mapped_messages}
        if system_msg:
            parts = payload.get("systemInstruction", {}).get("parts", [])
            parts.append({"text": system_msg})
            payload["systemInstruction"] = {"parts": parts}
        if tools:
            payload["tools"] = self._map_tools(tools)

        response = requests.post(
            url, headers=headers, params=params, json=payload, timeout=timeout
        )
        if not response.ok:
            body = (response.text or "").strip()[:2000]
            raise ProviderError(f"{response.status_code} {response.reason}: {body}")

        data = response.json()
        self._last_usage = data.get("usageMetadata", {})
        content = ""
        tool_calls = []
        for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            if "text" in part:
                content += part["text"]
            if "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(
                    {
                        "id": fc.get("name", "call_0"),
                        "type": "function",
                        "function": {
                            "name": fc.get("name", ""),
                            "arguments": json.dumps(
                                fc.get("args", {}), ensure_ascii=False
                            ),
                        },
                    }
                )
        message = {"role": "assistant", "content": content or None}
        if tool_calls:
            message["tool_calls"] = tool_calls
        return message
