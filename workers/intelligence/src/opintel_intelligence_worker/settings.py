"""Locked production settings for the deterministic M2-M5 worker."""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class IntelligenceWorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPINTEL_", extra="ignore")

    app_env: Literal["phase1"] = "phase1"
    database_host: str
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "opintel_phase1"
    database_username: str = "phase1_admin"
    database_password: SecretStr
    worker_poll_seconds: float = Field(default=0.25, ge=0.05, le=10)
    kill_switch_parameter: str
    aws_region: str = "us-east-2"
    ai_enabled: Literal[False] = False
    delivery_enabled: Literal[False] = False

    def database_url(self) -> str:
        return (
            "postgresql+psycopg://"
            f"{quote_plus(self.database_username)}:"
            f"{quote_plus(self.database_password.get_secret_value())}@"
            f"{self.database_host}:{self.database_port}/{self.database_name}?sslmode=require"
        )
