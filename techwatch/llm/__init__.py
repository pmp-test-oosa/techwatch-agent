"""Pluggable LLM providers, selected with LLM_PROVIDER or --provider."""
from __future__ import annotations

from .base import LLMError, Provider


def get_provider(name: str, max_calls: int) -> Provider:
    if name == "mock":
        from .mock import MockProvider
        return MockProvider(max_calls)
    if name == "claude_subscription":
        from .claude_subscription import ClaudeSubscriptionProvider
        return ClaudeSubscriptionProvider(max_calls)
    raise LLMError(f"unknown LLM provider {name!r} (use 'claude_subscription' or 'mock')")


__all__ = ["get_provider", "LLMError", "Provider"]
