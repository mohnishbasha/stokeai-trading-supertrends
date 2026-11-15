# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Environment settings (ARCHITECTURE section 13.4).

Every variable uses the SUPERTRENDS_ prefix. Secrets are SecretStr so they never appear in
repr or logs. Invalid values raise ConfigError naming the variable.
"""

import os
from typing import Annotated, Literal

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from supertrends.errors import ConfigError
from supertrends.version import DEFAULT_SOURCE_URL

_PREFIX = "SUPERTRENDS_"
DEV_API_TOKEN = "dev-token"  # noqa: S105 (documented dev-only default, rejected in stage and prod)
DEFAULT_DATABASE_URL = "postgresql+psycopg://supertrends:supertrends@localhost:5432/supertrends"


class Settings(BaseSettings):
    """Process settings read from the environment."""

    model_config = SettingsConfigDict(env_prefix=_PREFIX, extra="ignore", frozen=True)

    env: Literal["dev", "ci", "stage", "prod"] = "dev"
    database_url: SecretStr = SecretStr(DEFAULT_DATABASE_URL)
    market_provider: Literal["fixture", "massive", "alternate"] = "fixture"
    fundamentals_provider: Literal["fixture", "massive"] = "fixture"
    massive_api_key: SecretStr = SecretStr("")
    massive_base_url: str = "https://api.massive.com"
    fundamentals_api_key: SecretStr = SecretStr("")
    alternate_api_key: SecretStr = SecretStr("")
    alternate_base_url: str = ""
    provider_rate_per_min: int = Field(default=5, gt=0)
    narrative_provider: Literal["template", "openai_compatible"] = "template"
    llm_base_url: str = "http://localhost:8089/v1"
    llm_model: str = "mock"
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_seconds: float = Field(default=8.0, gt=0)
    api_token: SecretStr = SecretStr(DEV_API_TOKEN)
    api_url: str = ""
    scoring_config: str = "config/scoring.yaml"
    run_cron: str = "30 17 * * 1-5"
    publication_deadline: str = Field(default="19:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    worker_poll_seconds: int = Field(default=5, gt=0)
    queued_run_timeout_seconds: int = Field(default=600, gt=0)
    write_rate_per_min: int = Field(default=30, gt=0)
    log_level: Literal["debug", "info", "warning", "error"] | None = None
    source_url: str = DEFAULT_SOURCE_URL
    allowed_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1"]
    )
    bind: str = Field(default="127.0.0.1:8080", pattern=r"^[^:\s]+:\d{1,5}$")
    ui_dir: str = "ui/dist"
    demo: bool = False
    fixture_seed: int = 20261114
    fixture_end_date: str = ""
    fixture_permissive: bool = False

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _split_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return [h.strip() for h in value.split(",") if h.strip()]
        return value

    @model_validator(mode="after")
    def _cross_checks(self) -> "Settings":
        token = self.api_token.get_secret_value()
        if self.env in ("stage", "prod") and token in ("", DEV_API_TOKEN):
            msg = "SUPERTRENDS_API_TOKEN must be set to a real token in stage and prod"
            raise ValueError(msg)
        if self.demo and self.market_provider != "fixture":
            msg = "SUPERTRENDS_DEMO requires SUPERTRENDS_MARKET_PROVIDER=fixture"
            raise ValueError(msg)
        return self

    @property
    def effective_log_level(self) -> str:
        """Log level, defaulting to debug in dev and info elsewhere."""
        return self.log_level or ("debug" if self.env == "dev" else "info")


def load_settings() -> Settings:
    """Read settings from the environment. A .env file is read only when SUPERTRENDS_ENV=dev."""
    env_file = ".env" if os.environ.get(f"{_PREFIX}ENV", "dev") == "dev" else None
    try:
        return Settings(_env_file=env_file)
    except ValidationError as exc:
        raise ConfigError(_describe(exc)) from exc


def _describe(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = [str(p) for p in err["loc"]]
        name = f"{_PREFIX}{loc[0].upper()}" if loc else "settings"
        parts.append(f"{name}: {err['msg']}")
    return "; ".join(parts)
