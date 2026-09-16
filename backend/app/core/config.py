"""Application configuration.

Loaded from environment variables (or a local ``.env``). See
``.kiro/steering/tech.md`` § Environment variables for the full list and which
are required.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Required ---
    turso_database_url: str
    turso_auth_token: str
    jwt_secret_key: str
    cors_origins: str

    # --- Optional ---
    token_encryption_key: str | None = None
    # LLM: any OpenAI-compatible endpoint. Default is Groq's free tier.
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "openai/gpt-oss-120b"
    # Cap on completion tokens per request. Kept modest because providers
    # (Groq free tier especially) count max_tokens toward the per-minute budget
    # and reject the whole request with 413 if it alone exceeds the limit.
    llm_max_tokens: int = 2048
    environment: str = "dev"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_enabled(self) -> bool:
        """Whether the LLM-backed features are configured (see feature flags)."""
        return bool(self.llm_api_key)

    @property
    def is_prod(self) -> bool:
        return self.environment.lower() == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
