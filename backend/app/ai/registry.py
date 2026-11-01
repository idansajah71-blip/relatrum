"""Provider registry: single factory based on settings, deterministic by default."""
from __future__ import annotations

from functools import lru_cache

from app.ai.base import AIProvider
from app.ai.mock import MockProvider
from app.config import get_settings


class UnsupportedProviderError(Exception):
    pass


def build_provider(settings=None) -> AIProvider:
    settings = settings or get_settings()
    if settings.ai_provider == "mock":
        return MockProvider()
    if settings.ai_provider == "gemini":
        from app.ai.gemini import GeminiProvider

        return GeminiProvider(
            api_key=settings.gemini_api_key or "",
            model=settings.gemini_model,
            timeout_seconds=settings.ai_timeout_seconds,
            retry_limit=settings.ai_retry_limit,
        )
    if settings.ai_provider == "groq":
        from app.ai.groq import GroqProvider

        return GroqProvider(
            api_key=settings.groq_api_key or "",
            model=settings.groq_model,
            timeout_seconds=settings.ai_timeout_seconds,
            retry_limit=settings.ai_retry_limit,
        )
    raise UnsupportedProviderError(f"Unknown AI provider: {settings.ai_provider}")


@lru_cache
def default_provider_name() -> str:
    return get_settings().ai_provider
