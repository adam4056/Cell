import json
import os
import yaml

from core.providers.base import BaseProvider, ProviderError
from core.providers.openai_compat import OpenAICompatProvider
from core.providers.anthropic import AnthropicProvider
from core.providers.gemini import GeminiProvider

_PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "openai_compat": OpenAICompatProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}

_config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
with open(_config_path, "r", encoding="utf-8") as _f:
    _raw_cfg = yaml.safe_load(_f) or {}

_keys_path = os.path.join(os.path.expanduser("~"), ".cell-2", "keys.json")
_keys: dict = {}
if os.path.exists(_keys_path):
    with open(_keys_path, "r", encoding="utf-8") as _f:
        _keys = json.loads(_f.read() or "{}")


def _resolve_credentials(provider_id: str, provider_cfg: dict) -> dict:
    cfg = dict(provider_cfg)
    if not cfg.get("api_key"):
        cfg["api_key"] = _keys.get(provider_id, {}).get("api_key", "")
    return cfg


def get_provider(name: str | None = None) -> BaseProvider:
    providers_cfg = _raw_cfg.get("providers") or {}
    default_name = (
        _raw_cfg.get("default_provider")
        or next(iter(providers_cfg), None)
        or "openai_compat"
    )

    provider_name = name or default_name

    if isinstance(providers_cfg, dict) and provider_name in providers_cfg:
        cfg = _resolve_credentials(provider_name, providers_cfg[provider_name])
        provider_type = cfg.get("type", provider_name)
    else:
        api_base = (_raw_cfg.get("api_base") or "https://api.deepseek.com").rstrip("/")
        api_key = _raw_cfg.get("api_key") or _raw_cfg.get("deepseek_api_key", "")
        model = _raw_cfg.get("model") or "deepseek-chat"
        cheap_model = _raw_cfg.get("cheap_model") or model
        provider_type = "openai_compat"
        cfg = {
            "type": "openai_compat",
            "api_base": api_base,
            "api_key": api_key,
            "model": model,
            "cheap_model": cheap_model,
        }

    provider_type = cfg.get("type", provider_type)
    cls = _PROVIDER_REGISTRY.get(provider_type)
    if cls is None:
        raise ProviderError(f"Unknown provider type: {provider_type}")

    return cls(cfg)


def list_providers() -> list[str]:
    providers_cfg = _raw_cfg.get("providers") or {}
    return list(providers_cfg.keys())
