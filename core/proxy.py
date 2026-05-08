import os
import threading

from core.providers import get_provider, list_providers, ProviderError

DEFAULT_TIMEOUT = 60

_lock = threading.Lock()
_provider_name: str | None = None
_cheap_provider_name: str | None = None

_cache: dict[str, object] = {}


def _get(name: str | None = None) -> object:
    key = name or "__default__"
    with _lock:
        if key not in _cache:
            _cache[key] = get_provider(name)
    return _cache[key]


def get_last_usage() -> dict:
    return _get(_provider_name).get_last_usage()  # type: ignore[union-attr]


def set_model(model_name: str) -> None:
    global _provider_name
    _provider_name = model_name
    _cache.pop("__default__", None)
    _cache.pop(model_name, None)


def set_cheap_model(model_name: str) -> None:
    global _cheap_provider_name
    _cheap_provider_name = model_name


def chat(
    messages: list,
    tools: list | None = None,
    model: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    cheap: bool = False,
) -> dict:
    provider = _get(_cheap_provider_name if cheap else _provider_name)
    return provider.chat(  # type: ignore[union-attr]
        messages=messages,
        tools=tools,
        model=model,
        timeout=timeout,
    )


def request(
    messages: list,
    model: str | None = None,
    cheap: bool = False,
) -> str:
    return chat(messages, model=model, cheap=cheap).get("content", "")


ProxyAPIError = ProviderError
