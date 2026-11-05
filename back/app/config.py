from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "CineQuote AI API"
    app_env: str = "development"
    frontend_url: AnyHttpUrl = AnyHttpUrl("http://localhost:5173")
    database_url: str = "sqlite:///./cinequote.db"
    session_secret: SecretStr | None = None
    ai_provider: Literal["groq", "openai", "fallback"] = "groq"
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-20b"
    groq_max_completion_tokens: int = Field(default=128, ge=32, le=512)
    groq_timeout_seconds: float = Field(default=8.0, gt=0, le=30)
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-6-luna"
    openai_max_output_tokens: int = Field(default=80, ge=16, le=200)
    openai_timeout_seconds: float = Field(default=8.0, gt=0, le=30)
    hint_rate_limit_requests: int = Field(default=10, ge=1, le=1000)
    hint_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    hint_cache_enabled: bool = True
    auth_cookie_name: str = "cinequote_session"
    auth_session_days: int = Field(default=30, ge=1, le=365)
    auth_max_sessions_per_user: int = Field(default=10, ge=1, le=100)
    auth_cookie_secure: bool = False
    auth_cookie_samesite: Literal["lax", "strict"] = "lax"
    csrf_origin_check_enabled: bool = False
    trust_proxy_headers: bool = False
    proxy_shared_secret: SecretStr | None = None
    require_proxy_secret: bool = False
    login_rate_limit_ip_requests: int = Field(default=20, ge=1, le=1000)
    login_rate_limit_account_requests: int = Field(default=8, ge=1, le=1000)
    login_rate_limit_window_seconds: int = Field(default=900, ge=1, le=86400)
    register_rate_limit_ip_requests: int = Field(default=5, ge=1, le=1000)
    register_rate_limit_window_seconds: int = Field(default=3600, ge=1, le=86400)
    ai_user_rate_limit_requests: int = Field(default=30, ge=1, le=10000)
    ai_ip_rate_limit_requests: int = Field(default=60, ge=1, le=10000)
    ai_rate_limit_window_seconds: int = Field(default=3600, ge=1, le=86400)
    ai_global_rate_limit_requests: int = Field(default=300, ge=1, le=100000)
    ai_global_rate_limit_window_seconds: int = Field(default=3600, ge=1, le=86400)
    quiz_session_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    quiz_session_max_active: int = Field(default=2000, ge=10, le=100000)
    coach_rate_limit_requests: int = Field(default=5, ge=1, le=100)
    coach_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    recommendation_rate_limit_requests: int = Field(default=5, ge=1, le=100)
    recommendation_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    explanation_rate_limit_requests: int = Field(default=10, ge=1, le=100)
    explanation_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    custom_quiz_rate_limit_requests: int = Field(default=10, ge=1, le=100)
    custom_quiz_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("groq_api_key", "openai_api_key", "proxy_shared_secret", "session_secret", mode="before")
    @classmethod
    def empty_api_key_means_unconfigured(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_three_for_postgres(cls, value: object) -> object:
        """Render supplies postgresql:// URLs; SQLAlchemy needs an explicit Psycopg 3 dialect."""
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if self.app_env.casefold() != "production":
            return self
        errors: list[str] = []
        if not self.database_url.startswith("postgresql+psycopg://"):
            errors.append("DATABASE_URL must use PostgreSQL in production")
        if not str(self.frontend_url).startswith("https://"):
            errors.append("FRONTEND_URL must use HTTPS in production")
        if not self.auth_cookie_secure or self.auth_cookie_samesite != "strict":
            errors.append("production cookies require AUTH_COOKIE_SECURE=true and AUTH_COOKIE_SAMESITE=strict")
        if not self.csrf_origin_check_enabled:
            errors.append("CSRF_ORIGIN_CHECK_ENABLED must be true in production")
        if not self.trust_proxy_headers or not self.require_proxy_secret:
            errors.append("TRUST_PROXY_HEADERS and REQUIRE_PROXY_SECRET must be true in production")
        proxy_secret = self.proxy_shared_secret.get_secret_value() if self.proxy_shared_secret else ""
        session_secret = self.session_secret.get_secret_value() if self.session_secret else ""
        if len(proxy_secret) < 32:
            errors.append("PROXY_SHARED_SECRET must contain at least 32 characters")
        if len(session_secret) < 32:
            errors.append("SESSION_SECRET must contain at least 32 characters")
        if errors:
            raise ValueError("; ".join(errors))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

