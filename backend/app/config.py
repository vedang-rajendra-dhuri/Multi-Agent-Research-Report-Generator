from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
from typing import Literal

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "ReportPilot"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: SecretStr | None = None
    database_sslmode: str = "require"
    secret_key: SecretStr | None = None
    llm_provider: Literal["openai", "gemini"] | None = None
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    search_provider: Literal["tavily"] | None = None
    search_provider_api_key: SecretStr | None = None
    llm_model: str | None = None
    max_research_iterations: int = Field(default=2, ge=1, le=5)
    max_search_results: int = Field(default=8, ge=1, le=20)
    provider_timeout_seconds: int = Field(default=60, ge=5, le=120)
    worker_poll_seconds: int = Field(default=2, ge=1, le=30)
    access_token_minutes: int = Field(default=15, gt=0, le=60)
    refresh_token_days: int = Field(default=30, gt=0, le=365)
    cors_origins: list[str] = ["http://localhost:5173"]

    @field_validator("database_sslmode")
    @classmethod
    def validate_sslmode(cls, value: str) -> str:
        allowed = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
        if value not in allowed:
            raise ValueError(f"DATABASE_SSLMODE must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator(
        "llm_provider",
        "search_provider",
        "llm_model",
        "openai_api_key",
        "gemini_api_key",
        "search_provider_api_key",
        mode="before",
    )
    @classmethod
    def empty_optional_provider_values_are_unset(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str], info: ValidationInfo) -> list[str]:
        if not origins:
            raise ValueError("CORS_ORIGINS must contain at least one explicit origin.")
        normalized: list[str] = []
        is_production = str(info.data.get("app_env", "development")).lower() == "production"
        for origin in origins:
            origin = origin.strip().rstrip("/")
            parsed = urlsplit(origin)
            if (
                origin == "*"
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
                or (is_production and parsed.scheme != "https")
            ):
                raise ValueError("CORS_ORIGINS must list explicit, valid frontend origins.")
            try:
                parsed.port
            except ValueError as error:
                raise ValueError("CORS_ORIGINS must list explicit, valid frontend origins.") from error
            normalized.append(origin)
        return normalized

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()