"""Environment-only settings for local M0 adapters."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LocalSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OPINTEL_",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test"] = "development"
    database_url: str = "sqlite:///./local-data/m0.db"
    fixture_root: Path = Path("fixtures/public-web")
    auth_token: SecretStr
    auth_subject: str = "local-operator"
    workspace_id: UUID
    allowed_origins: str = "http://127.0.0.1:3000,http://localhost:3000"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1024, le=65535)
    worker_poll_seconds: float = Field(default=0.25, ge=0.05, le=10)
    worker_lease_seconds: int = Field(default=30, ge=5, le=300)

    @field_validator("database_url")
    @classmethod
    def local_sqlite_only(cls, value: str) -> str:
        if not value.startswith("sqlite:///"):
            raise ValueError("M0 local adapter accepts only sqlite:/// database URLs")
        return value

    @field_validator("auth_subject")
    @classmethod
    def nonempty_subject(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("auth subject must not be empty")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_local_settings() -> LocalSettings:
    return LocalSettings()  # type: ignore[call-arg]
