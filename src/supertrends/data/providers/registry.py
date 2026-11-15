# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Provider registry (ARCHITECTURE section 7.4).

`market_provider(settings)` and `fundamentals_provider(settings)` pick an implementation from
`Settings.market_provider` and `Settings.fundamentals_provider`. The two are chosen
independently, so a market provider and a fundamentals provider from different vendors can be
mixed.

Implementations plug in without editing this module's callers or each other's code. Each table
maps a name to a lazy "module:attribute" target resolved on first use, where the attribute is a
`from_settings(settings)` callable. S1-T03 supplies `fixture`, S1-T04 `massive`, S1-T05
`alternate`; until a module exists the registry fails with a clear ConfigError. Tests and
extensions may call `register_market_provider` and `register_fundamentals_provider`.
"""

from collections.abc import Callable
from importlib import import_module

from supertrends.data.providers.base import FundamentalsProvider, MarketDataProvider
from supertrends.errors import ConfigError
from supertrends.settings import Settings

_P = "supertrends.data.providers"
_Factory = Callable[[Settings], object]

_MARKET: dict[str, str | _Factory] = {
    "fixture": f"{_P}.fixture:FixtureProvider.from_settings",
    "massive": f"{_P}.massive:MassiveProvider.from_settings",
    "alternate": f"{_P}.alternate:AlternateProvider.from_settings",  # ADR-032
}
_FUNDAMENTALS: dict[str, str | _Factory] = {
    "fixture": f"{_P}.fixture:FixtureFundamentals.from_settings",
    "massive": f"{_P}.massive:MassiveFundamentals.from_settings",
}


def register_market_provider(name: str, factory: Callable[[Settings], MarketDataProvider]) -> None:
    """Add or replace a market provider factory."""
    _MARKET[name] = factory


def register_fundamentals_provider(
    name: str, factory: Callable[[Settings], FundamentalsProvider]
) -> None:
    """Add or replace a fundamentals provider factory."""
    _FUNDAMENTALS[name] = factory


def market_provider_names() -> list[str]:
    """Allowed values of SUPERTRENDS_MARKET_PROVIDER."""
    return list(_MARKET)


def fundamentals_provider_names() -> list[str]:
    """Allowed values of SUPERTRENDS_FUNDAMENTALS_PROVIDER."""
    return list(_FUNDAMENTALS)


def _resolve(table: dict[str, str | _Factory], setting: str, name: str) -> _Factory:
    entry = table.get(name)
    if entry is None:
        msg = f"{setting}={name!r} is not one of: {', '.join(table)}"
        raise ConfigError(msg)
    if callable(entry):
        return entry
    module_name, _, attr_path = entry.partition(":")
    try:
        target: object = import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise
        msg = f"{setting}={name!r} has no implementation yet (module {module_name} is missing)"
        raise ConfigError(msg) from exc
    try:
        for part in attr_path.split("."):
            target = getattr(target, part)
    except AttributeError as exc:
        msg = f"{setting}={name!r} has no implementation yet ({entry} is missing)"
        raise ConfigError(msg) from exc
    if not callable(target):
        msg = f"{setting}={name!r} is misregistered ({entry} is not callable)"
        raise ConfigError(msg)
    return target


def market_provider(settings: Settings) -> MarketDataProvider:
    """Build the market data provider named by settings. Raises ConfigError when unknown."""
    provider = _resolve(_MARKET, "SUPERTRENDS_MARKET_PROVIDER", settings.market_provider)(settings)
    if not isinstance(provider, MarketDataProvider):
        msg = f"SUPERTRENDS_MARKET_PROVIDER={settings.market_provider!r} does not build a provider"
        raise ConfigError(msg)
    return provider


def fundamentals_provider(settings: Settings) -> FundamentalsProvider:
    """Build the fundamentals provider named by settings. Raises ConfigError when unknown."""
    provider = _resolve(
        _FUNDAMENTALS, "SUPERTRENDS_FUNDAMENTALS_PROVIDER", settings.fundamentals_provider
    )(settings)
    if not isinstance(provider, FundamentalsProvider):
        name = settings.fundamentals_provider
        msg = f"SUPERTRENDS_FUNDAMENTALS_PROVIDER={name!r} does not build a provider"
        raise ConfigError(msg)
    return provider
