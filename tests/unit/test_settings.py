# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Environment settings model (ARCHITECTURE section 13.4)."""

import pytest

from supertrends.errors import ConfigError
from supertrends.settings import Settings, load_settings


def test_settings_defaults_are_dev_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPERTRENDS_ENV", raising=False)
    s = Settings()
    assert s.env == "dev"
    assert s.market_provider == "fixture"
    assert s.bind == "127.0.0.1:8080"
    assert s.api_token.get_secret_value() == "dev-token"
    assert s.source_url == "https://github.com/mohnishbasha/stokeai-trading-supertrends"
    assert s.allowed_hosts == ["localhost", "127.0.0.1"]


def test_settings_invalid_value_fails_naming_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERTRENDS_MARKET_PROVIDER", "yahoo")
    with pytest.raises(ConfigError, match="SUPERTRENDS_MARKET_PROVIDER"):
        load_settings()


def test_settings_stage_with_dev_token_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERTRENDS_ENV", "stage")
    monkeypatch.delenv("SUPERTRENDS_API_TOKEN", raising=False)
    with pytest.raises(ConfigError, match="SUPERTRENDS_API_TOKEN"):
        load_settings()


def test_settings_prod_with_real_token_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERTRENDS_ENV", "prod")
    monkeypatch.setenv("SUPERTRENDS_API_TOKEN", "x" * 32)
    assert load_settings().env == "prod"


def test_settings_secret_not_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERTRENDS_MASSIVE_API_KEY", "super-secret-value")
    assert "super-secret-value" not in repr(load_settings())


def test_settings_allowed_hosts_parses_comma_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERTRENDS_ALLOWED_HOSTS", "a.example, b.example")
    assert load_settings().allowed_hosts == ["a.example", "b.example"]


def test_settings_demo_requires_fixture_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERTRENDS_DEMO", "1")
    monkeypatch.setenv("SUPERTRENDS_MARKET_PROVIDER", "massive")
    with pytest.raises(ConfigError, match="SUPERTRENDS_DEMO"):
        load_settings()
