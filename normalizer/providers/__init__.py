"""Normalizer providers package."""

from __future__ import annotations

from typing import Any

from normalizer.providers.agent_file import AgentFileProvider
from normalizer.providers.api import ApiProvider
from normalizer.providers.protocol import NormalizerProvider


def get_provider(name: str = "agent_file", **kwargs: Any) -> NormalizerProvider:
    """Factory creating configured NormalizerProvider instances."""
    if name == "agent_file":
        return AgentFileProvider(**kwargs)
    if name == "api":
        return ApiProvider(**kwargs)
    raise ValueError(f"Unknown provider: {name}. Supported providers are 'agent_file' and 'api'.")


__all__ = [
    "AgentFileProvider",
    "ApiProvider",
    "NormalizerProvider",
    "get_provider",
]
