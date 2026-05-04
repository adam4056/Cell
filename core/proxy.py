import os
import requests
import yaml

DEFAULT_TIMEOUT = 60

_config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_config_path, "r", encoding="utf-8") as _f:
    _cfg = yaml.safe_load(_f) or {}

# OpenAI-compatible config (works for Ollama via /v1, DeepSeek, etc.)
_api_base = (_cfg.get("api_base") or "https://api.deepseek.com").rstrip("/")
_api_key = _cfg.get("api_key") or _cfg.get("deepseek_api_key", "") or "noauth"
DEFAULT_MODEL = _cfg.get("model") or "deepseek-chat"
API_URL = _api_base + "/chat/completions"


class ProxyAPIError(Exception):
    pass


_last_usage: dict = {}


def get_last_usage() -> dict:
    return _last_usage


def chat(messages: list, tools: list | None = None, model: str | None = None, timeout: int = DEFAULT_TIMEOUT) -> dict:
    global _last_usage
    payload = {"model": model or DEFAULT_MODEL, "messages": messages}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    response = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    if not response.ok:
        body = (response.text or "").strip()[:2000]
        raise ProxyAPIError(f"{response.status_code} {response.reason}: {body}")
    data = response.json()
    _last_usage = data.get("usage", {})
    return data["choices"][0]["message"]


def request(messages: list, model: str | None = None) -> str:
    return chat(messages, model=model).get("content", "")
