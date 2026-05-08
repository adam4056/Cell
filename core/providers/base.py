from abc import ABC, abstractmethod
from typing import Any


class ProviderError(Exception):
    pass


class BaseProvider(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.model = config.get("model", "")
        self.cheap_model = config.get("cheap_model", self.model)
        self._last_usage: dict = {}

    def get_last_usage(self) -> dict:
        return self._last_usage

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        timeout: int = 120,
    ) -> dict: ...
