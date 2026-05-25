import os
import re
import threading

from core.providers import get_provider, list_providers, ProviderError

DEFAULT_TIMEOUT = 60

_lock = threading.Lock()
_provider_name: str | None = None
_cheap_provider_name: str | None = None

_cache: dict[str, object] = {}

_TRIVIAL_PATTERNS = re.compile(
    r"^(hi|hey|hello|good\s*(morning|evening|night|afternoon)|thanks|thank\s*you|ok|okay|yes|no|sure|got\s*it|right|cool|great|nice|bye|goodbye|see\s*ya|yo|sup|what'?s?\s*up|howdy|brb|lol|haha|ha)\b",
    re.IGNORECASE,
)

_COMPLEX_INDICATORS = (
    "search",
    "find",
    "browse",
    "fetch",
    "download",
    "write",
    "create",
    "build",
    "make",
    "generate",
    "code",
    "program",
    "debug",
    "fix",
    "refactor",
    "implement",
    "design",
    "analyze",
    "compare",
    "explain",
    "calculate",
    "compute",
    "convert",
    "translate",
    "summarize",
    "summarise",
    "schedule",
    "remember",
    "self_improve",
    "api",
    "database",
    "deploy",
    "test",
)


def _classify_complexity(user_message: str, has_tools: bool = False) -> str:
    """Return 'trivial', 'medium', or 'complex' based on heuristic analysis."""
    text = user_message.strip()
    if not text:
        return "medium"

    word_count = len(text.split())

    if has_tools:
        return "complex"

    for indicator in _COMPLEX_INDICATORS:
        if indicator in text.lower():
            return "complex"

    if word_count <= 6 and _TRIVIAL_PATTERNS.match(text):
        return "trivial"

    if word_count <= 10 and text.endswith("?") and word_count <= 5:
        return "trivial"

    if word_count <= 4:
        return "trivial"

    return "medium"


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
    auto_route: bool = False,
) -> dict:
    use_cheap = cheap
    if auto_route and not cheap:
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                content = m.get("content", "")
                if isinstance(content, list):
                    for b in content:
                        if b.get("type") == "text":
                            user_msg = b.get("text", "")
                            break
                else:
                    user_msg = str(content)
                break
        complexity = _classify_complexity(user_msg, has_tools=bool(tools))
        use_cheap = complexity == "trivial"
    provider = _get(_cheap_provider_name if use_cheap else _provider_name)
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
