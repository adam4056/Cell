import os
import requests
import yaml

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT = 60

_config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_config_path, "r", encoding="utf-8") as _f:
    _api_key = yaml.safe_load(_f).get("deepseek_api_key", "")


class ProxyAPIError(Exception):
    pass


_last_usage: dict = {}


def get_last_usage() -> dict:
    return _last_usage


def chat(messages: list, tools: list | None = None, model: str = DEFAULT_MODEL, timeout: int = DEFAULT_TIMEOUT) -> dict:
    global _last_usage
    payload = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    response = requests.post(
        DEEPSEEK_API_URL,
        headers={"Authorization": f"Bearer {_api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    if not response.ok:
        body = (response.text or "").strip()[:2000]
        raise ProxyAPIError(f"{response.status_code} {response.reason}: {body}")
    data = response.json()
    _last_usage = data.get("usage", {})
    return data["choices"][0]["message"]


def request(messages: list, model: str = DEFAULT_MODEL) -> str:
    return chat(messages, model=model).get("content", "")
