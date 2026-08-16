"""Credential-free settings for the hostile-content research worker."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ResearchWorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OPINTEL_",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test"] = "development"
    database_url: str = "sqlite:///./local-data/m0.db"
    worker_poll_seconds: float = Field(default=0.25, ge=0.05, le=10)
    worker_lease_seconds: int = Field(default=30, ge=5, le=300)
    research_live_enabled: bool = False
    research_browser_enabled: bool = False

    @field_validator("database_url")
    @classmethod
    def local_sqlite_only(cls, value: str) -> str:
        if not value.startswith("sqlite:///"):
            raise ValueError("local research accepts only sqlite:/// database URLs")
        return value


@lru_cache(maxsize=1)
def get_research_worker_settings() -> ResearchWorkerSettings:
    return ResearchWorkerSettings()
