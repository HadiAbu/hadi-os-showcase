"""Task 0.2 — Settings loads from the environment; missing required vars raise."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE = dict(
    turso_database_url="https://db.turso.io",
    turso_auth_token="tok",
    jwt_secret_key="secret",
    cors_origins="http://localhost:5173, http://localhost:8080",
)

REQUIRED_ENV = ["TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN", "JWT_SECRET_KEY", "CORS_ORIGINS"]


def test_loads_from_values_with_sane_defaults():
    s = Settings(_env_file=None, **BASE)
    assert s.llm_model == "openai/gpt-oss-120b"
    assert s.llm_base_url == "https://api.groq.com/openai/v1"
    assert s.environment == "dev"
    assert s.is_prod is False
    assert s.ai_enabled is False
    assert s.cors_origins_list == ["http://localhost:5173", "http://localhost:8080"]


def test_ai_enabled_true_when_key_present():
    s = Settings(_env_file=None, llm_api_key="gsk_test", **BASE)
    assert s.ai_enabled is True


def test_is_prod_true_when_environment_prod():
    s = Settings(_env_file=None, environment="prod", **BASE)
    assert s.is_prod is True


def test_missing_required_raises(monkeypatch):
    for key in REQUIRED_ENV:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
