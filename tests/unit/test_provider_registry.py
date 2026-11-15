# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Provider registry and error types (TS-ING-007, TS-ING-008, TS-ING-044)."""

import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from supertrends.data.providers import registry
from supertrends.errors import (
    CapabilityNotSupported,
    ConfigError,
    ProviderError,
    ProviderRateLimited,
    SuperTrendsError,
)
from supertrends.settings import Settings, load_settings
from tests.contract.fakes import FakeFundamentals, FakeProvider


@pytest.fixture(autouse=True)
def _restore_tables() -> Iterator[None]:
    market, fundamentals = dict(registry._MARKET), dict(registry._FUNDAMENTALS)
    yield
    registry._MARKET.clear()
    registry._MARKET.update(market)
    registry._FUNDAMENTALS.clear()
    registry._FUNDAMENTALS.update(fundamentals)


def test_unit_provider_registry_unknown_name_fails_startup_with_clear_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERTRENDS_MARKET_PROVIDER", "nope")
    with pytest.raises(ConfigError) as exc:
        load_settings()
    assert "SUPERTRENDS_MARKET_PROVIDER" in str(exc.value)
    assert "fixture" in str(exc.value)


def test_unit_provider_registry_unknown_name_in_table_names_setting_and_allowed_values() -> None:
    s = Settings.model_construct(market_provider="x", fundamentals_provider="y")  # type: ignore[arg-type]
    with pytest.raises(ConfigError) as exc:
        registry.market_provider(s)
    assert str(exc.value) == (
        "SUPERTRENDS_MARKET_PROVIDER='x' is not one of: fixture, massive, alternate"
    )
    with pytest.raises(ConfigError) as exc2:
        registry.fundamentals_provider(s)
    assert (
        str(exc2.value) == "SUPERTRENDS_FUNDAMENTALS_PROVIDER='y' is not one of: fixture, massive"
    )


def test_unit_provider_registry_registered_name_without_implementation_fails_clearly() -> None:
    registry._MARKET["alternate"] = "supertrends.data.providers.no_such_module:Nope.from_settings"
    with pytest.raises(ConfigError, match="no implementation yet"):
        registry.market_provider(Settings(market_provider="alternate"))


def test_unit_provider_registry_env_switch_changes_active_provider_without_code_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry.register_market_provider("fixture", lambda _s: FakeProvider(name="one"))
    registry.register_market_provider("massive", lambda _s: FakeProvider(name="two"))
    monkeypatch.setenv("SUPERTRENDS_MARKET_PROVIDER", "fixture")
    assert registry.market_provider(load_settings()).name == "one"
    monkeypatch.setenv("SUPERTRENDS_MARKET_PROVIDER", "massive")
    assert registry.market_provider(load_settings()).name == "two"


def test_unit_provider_registry_mixes_market_and_fundamentals_from_different_vendors() -> None:
    registry.register_market_provider("alternate", lambda _s: FakeProvider(name="vendor-a"))
    registry.register_fundamentals_provider("massive", lambda _s: FakeFundamentals(name="vendor-b"))
    s = Settings(market_provider="alternate", fundamentals_provider="massive")
    assert registry.market_provider(s).name == "vendor-a"
    assert registry.fundamentals_provider(s).name == "vendor-b"


def test_unit_provider_registry_non_provider_factory_result_is_config_error() -> None:
    registry.register_market_provider("fixture", lambda _s: object())  # type: ignore[arg-type,return-value]
    with pytest.raises(ConfigError, match="does not build a provider"):
        registry.market_provider(Settings())


def test_unit_provider_registry_lists_allowed_names() -> None:
    assert registry.market_provider_names()[:3] == ["fixture", "massive", "alternate"]
    assert registry.fundamentals_provider_names()[:2] == ["fixture", "massive"]


def test_unit_provider_errors_derive_from_provider_error() -> None:
    assert issubclass(ProviderError, SuperTrendsError)
    assert issubclass(CapabilityNotSupported, ProviderError)
    err = ProviderRateLimited(retry_after=2.5)
    assert err.retry_after == 2.5
    assert isinstance(err, ProviderError)
    assert ProviderRateLimited().retry_after is None


def test_unit_provider_registry_lazy_target_resolves_from_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = ModuleType("st_fake_impl")
    mod.FakeFactory = type(  # type: ignore[attr-defined]
        "FakeFactory", (), {"from_settings": staticmethod(lambda _s: FakeProvider(name="lazy"))}
    )
    monkeypatch.setitem(sys.modules, "st_fake_impl", mod)
    registry._MARKET["alternate"] = "st_fake_impl:FakeFactory.from_settings"
    assert registry.market_provider(Settings(market_provider="alternate")).name == "lazy"


def test_unit_provider_registry_module_without_attribute_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "st_fake_impl", ModuleType("st_fake_impl"))
    registry._MARKET["alternate"] = "st_fake_impl:Missing.from_settings"
    with pytest.raises(ConfigError, match="no implementation yet"):
        registry.market_provider(Settings(market_provider="alternate"))


def test_unit_provider_registry_non_callable_target_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = ModuleType("st_fake_impl")
    mod.VALUE = 3  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "st_fake_impl", mod)
    registry._MARKET["alternate"] = "st_fake_impl:VALUE"
    with pytest.raises(ConfigError, match="misregistered"):
        registry.market_provider(Settings(market_provider="alternate"))


def test_unit_provider_registry_missing_dependency_inside_module_is_not_masked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "st_broken_impl.py").write_text("import st_missing_dependency_xyz\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    registry._MARKET["alternate"] = "st_broken_impl:X.from_settings"
    with pytest.raises(ModuleNotFoundError, match="st_missing_dependency_xyz"):
        registry.market_provider(Settings(market_provider="alternate"))
