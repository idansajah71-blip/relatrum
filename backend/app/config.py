"""Application configuration via environment variables (12-factor)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "RELATRUM"
    app_version: str = "0.1.0"
    app_env: str = "development"  # development | testing | production
    log_level: str = "INFO"

    database_url: str = "sqlite:///./relatrum.db"

    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    ai_provider: str = "mock"  # mock | gemini | groq
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"

    max_upload_mb: int = 10
    max_document_pages: int = 100
    llm_max_calls_per_analysis: int = 5
    ai_timeout_seconds: int = 45
    ai_retry_limit: int = 2

    enable_local_embeddings: bool = False
    enable_ai_alignment: bool = False

    storage_dir: str = "./storage"

    cors_origins: str = "http://localhost:3000,http://localhost:4000"

    pipeline_version: str = "1.0.0"
    prompt_version: str = "1.0.0"

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        if self.ai_provider not in ("mock", "gemini", "groq"):
            raise ValueError(
                f"AI_PROVIDER must be one of mock|gemini|groq, got '{self.ai_provider}'"
            )
        if self.ai_provider in ("gemini", "groq") and not (
            self.gemini_api_key if self.ai_provider == "gemini" else self.groq_api_key
        ):
            raise ValueError(
                f"AI_PROVIDER={self.ai_provider} requires an API key. "
                "Set the key or use AI_PROVIDER=mock (deterministic, no key required)."
            )
        if self.app_env == "production" and self.jwt_secret == "dev-insecure-secret-change-me":
            raise ValueError("JWT_SECRET must be set in production")
        if self.max_upload_mb <= 0 or self.max_document_pages <= 0:
            raise ValueError("MAX_UPLOAD_MB and MAX_DOCUMENT_PAGES must be positive")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
