"""Unit tests: Settings validation (fail-fast configuration rules)."""
from __future__ import annotations

import pytest

from app.config import Settings


def test_default_settings_are_mock_provider():
    settings = Settings(_env_file=None, app_env="development")
    assert settings.ai_provider == "mock"
    assert settings.app_env == "development"


def test_gemini_without_key_rejected():
    with pytest.raises(ValueError, match="requires an API key"):
        Settings(_env_file=None, ai_provider="gemini")


def test_groq_without_key_rejected():
    with pytest.raises(ValueError, match="requires an API key"):
        Settings(_env_file=None, ai_provider="groq")


def test_gemini_with_key_accepted():
    settings = Settings(_env_file=None, ai_provider="gemini", gemini_api_key="k-test")
    assert settings.ai_provider == "gemini"


def test_unknown_provider_rejected():
    with pytest.raises(ValueError, match="AI_PROVIDER"):
        Settings(_env_file=None, ai_provider="openai")


def test_production_requires_strong_secret():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(_env_file=None, app_env="production", jwt_secret="dev-insecure-secret-change-me")


def test_production_with_secret_ok():
    settings = Settings(_env_file=None, app_env="production", jwt_secret="s" * 40)
    assert settings.app_env == "production"


def test_nonpositive_limits_rejected():
    with pytest.raises(ValueError, match="positive"):
        Settings(_env_file=None, max_upload_mb=0)


def test_cors_origin_list_parses():
    settings = Settings(_env_file=None, cors_origins="http://a, http://b,")
    assert settings.cors_origin_list == ["http://a", "http://b"]
