"""Credential-free settings for the hostile-content research worker."""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ResearchWorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OPINTEL_",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "phase1"] = "development"
    database_url: str = "sqlite:///./local-data/m0.db"
    worker_poll_seconds: float = Field(default=0.25, ge=0.05, le=10)
    worker_lease_seconds: int = Field(default=30, ge=5, le=300)
    research_live_enabled: bool = False
    research_browser_enabled: bool = False
    controlled_egress_url: str | None = None
    egress_policy_revision: str | None = None
    kill_switch_parameter: str | None = None
    aws_region: str = "us-east-2"
    database_host: str | None = None
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "opintel_phase1"
    database_username: str = "phase1_admin"
    database_password: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def supported_database(cls, value: str) -> str:
        scheme = urlsplit(value).scheme
        if scheme not in {"sqlite", "postgresql+psycopg"}:
            raise ValueError("database must use sqlite or postgresql+psycopg")
        return value

    def model_post_init(self, context: object, /) -> None:
        del context
        if self.app_env == "phase1":
            if not self.database_host or self.database_password is None:
                raise ValueError("Phase 1 requires explicit PostgreSQL host and secret")
            if not self.controlled_egress_url or not self.egress_policy_revision:
                raise ValueError("Phase 1 requires the controlled egress boundary")
            if not self.kill_switch_parameter:
                raise ValueError("Phase 1 requires an authoritative kill switch")
            if self.research_browser_enabled:
                raise ValueError("Phase 1 browser execution is disabled")
        elif not self.database_url.startswith("sqlite:///"):
            raise ValueError("local/test research requires an explicit sqlite:/// adapter")

    def resolved_database_url(self) -> str:
        if self.app_env != "phase1":
            return self.database_url
        from urllib.parse import quote_plus

        assert self.database_host is not None
        assert self.database_password is not None
        user = quote_plus(self.database_username)
        password = quote_plus(self.database_password.get_secret_value())
        return (
            f"postgresql+psycopg://{user}:{password}@{self.database_host}:"
            f"{self.database_port}/{self.database_name}?sslmode=require"
        )


@lru_cache(maxsize=1)
def get_research_worker_settings() -> ResearchWorkerSettings:
    return ResearchWorkerSettings()
