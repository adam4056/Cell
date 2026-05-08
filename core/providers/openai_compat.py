import requests

from core.providers.base import BaseProvider, ProviderError


class OpenAICompatProvider(BaseProvider):
    def __init__(self, config: dict):
        super().__init__(config)
        self.api_base = (config.get("api_base") or "https://api.deepseek.com").rstrip(
            "/"
        )
        self.api_key = config.get("api_key") or "noauth"
        self.url = self.api_base + "/chat/completions"

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        timeout: int = 120,
    ) -> dict:
        request_model = model or self.model
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
