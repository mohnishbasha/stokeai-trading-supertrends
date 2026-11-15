# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Alternate provider (Alpaca Market Data) against recorded fixtures, no network.

TS-ING-006 (shared contract suite), TS-ING-100 to TS-ING-104. The recorded responses live in
tests/fixtures/providers/alpaca/ (synthetic values, scrubbed); `_FakeAlpaca` replays them behind
`httpx.MockTransport` and applies the `start`, `end`, and `page_token` query parameters the way
the vendor does.
"""

import importlib.util
import json
import logging
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from supertrends.data.providers import registry
from supertrends.data.providers.alternate import AlternateProvider
from supertrends.data.providers.base import MarketDataProvider
from supertrends.errors import (
    CapabilityNotSupported,
    ConfigError,
    ProviderDataError,
    ProviderRateLimited,
    ProviderUnavailable,
    ProviderUnconfigured,
)
from supertrends.settings import load_settings
from tests.contract.fakes import FakeFundamentals
from tests.contract.provider_contract import MarketProviderContract

FIXTURES = Path(__file__).parent.parent / "fixtures" / "providers" / "alpaca"
SECRET = "s3cr3t-value-0123"  # noqa: S105
KEY = f"PKTESTKEYID:{SECRET}"
PAGE = 40


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text())
    return data


def _ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw).astimezone(UTC)


class _FakeAlpaca:
    """Replays recorded responses; records every request."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.daily = _load("daily_AAA.json")["bars"]["AAA"]
        self.intraday = _load("intraday_AAA.json")["bars"]["AAA"]
        self.actions = _load("corporate_actions_AAA.json")

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert request.headers["APCA-API-KEY-ID"] == "PKTESTKEYID"
        assert request.headers["APCA-API-SECRET-KEY"] == SECRET
        q = request.url.params
        if request.url.path == "/v2/stocks/bars":
            return self._bars(q)
        if request.url.path == "/v1/corporate-actions":
            if q["symbols"] != "AAA":
                return httpx.Response(200, json={"corporate_actions": {}, "next_page_token": None})
            return httpx.Response(200, json=self.actions)
        return httpx.Response(404)

    def _bars(self, q: httpx.QueryParams) -> httpx.Response:
        sym = q["symbols"]
        source = self.intraday if q["timeframe"] == "5Min" else self.daily
        lo, hi = _ts(q["start"]), _ts(q["end"])
        rows = [r for r in source if lo <= _ts(r["t"]) < hi] if sym == "AAA" else []
        offset = int(q.get("page_token", "0"))
        page = rows[offset : offset + PAGE]
        more = offset + PAGE < len(rows)
        return httpx.Response(
            200,
            json={
                "bars": {sym: page} if page else {},
                "next_page_token": str(offset + PAGE) if more else None,
            },
        )


def _provider(
    handler: Callable[[httpx.Request], httpx.Response], *, key: str = KEY, **kw: Any
) -> AlternateProvider:
    return AlternateProvider(
        key,
        transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
        jitter=lambda: 1.0,
        today=lambda: date(2026, 4, 10),
        **kw,
    )


class TestAlternateMarketContract(MarketProviderContract):
    known_symbol = "AAA"
    start = date(2026, 1, 5)
    end = date(2026, 3, 27)

    @pytest.fixture
    def provider(self) -> MarketDataProvider:
        return _provider(_FakeAlpaca())


# --------------------------------------------------------------- behavior


def test_unit_alternate_capabilities_intraday_on_grouped_and_trades_off() -> None:
    caps = _provider(_FakeAlpaca()).capabilities
    assert (caps.intraday, caps.adjusted, caps.grouped_daily, caps.trades, caps.reference) == (
        True,
        True,
        False,
        False,
        True,
    )


def test_unit_alternate_unsupported_methods_raise_without_network() -> None:
    fake = _FakeAlpaca()
    p = _provider(fake)
    with pytest.raises(CapabilityNotSupported):
        p.grouped_daily(date(2026, 1, 5))
    with pytest.raises(CapabilityNotSupported):
        p.trades("AAA", date(2026, 1, 5))
    assert fake.requests == []


def test_unit_alternate_daily_request_is_adjusted_header_authed_and_paginated() -> None:
    fake = _FakeAlpaca()
    bars = _provider(fake).daily_bars("AAA", date(2026, 1, 2), date(2026, 4, 10))
    assert len(bars) == len(fake.daily) > PAGE  # more than one page was followed
    assert len(fake.requests) >= 2
    first = fake.requests[0].url.params
    assert (first["timeframe"], first["adjustment"], first["feed"]) == ("1Day", "all", "iex")
    assert "page_token" in fake.requests[1].url.params
    assert bars[0].ts.date() == date(2026, 1, 2)
    assert bars[0].ts.tzinfo is not None
    for r in fake.requests:
        assert SECRET not in str(r.url)
        assert "PKTESTKEYID" not in str(r.url)


def test_unit_alternate_intraday_drops_extended_hours_and_uses_utc_starts() -> None:
    bars = _provider(_FakeAlpaca()).intraday_bars("AAA", date(2026, 1, 5), date(2026, 1, 5))
    assert len(bars) == 78
    assert bars[0].ts == datetime(2026, 1, 5, 14, 30, tzinfo=UTC)  # 09:30 EST
    assert bars[-1].ts == datetime(2026, 1, 5, 20, 55, tzinfo=UTC)


def test_unit_alternate_intraday_rejects_other_bar_sizes() -> None:
    with pytest.raises(CapabilityNotSupported):
        _provider(_FakeAlpaca()).intraday_bars("AAA", date(2026, 1, 5), date(2026, 1, 5), 15)  # type: ignore[arg-type]


def test_unit_alternate_corporate_actions_ratios_and_merged_dividends() -> None:
    actions = _provider(_FakeAlpaca()).corporate_actions("AAA", date(2026, 1, 1), date(2026, 6, 30))
    summary = [(a.ex_date.isoformat(), a.kind, a.ratio, a.amount) for a in actions]
    assert summary == [
        ("2026-02-06", "dividend", None, pytest.approx(0.30)),
        ("2026-02-17", "split", 4.0, None),
        ("2026-03-10", "split", pytest.approx(0.1), None),
        ("2026-05-08", "dividend", None, 0.26),
    ]
    narrow = _provider(_FakeAlpaca()).corporate_actions("AAA", date(2026, 2, 10), date(2026, 3, 1))
    assert [a.ex_date.isoformat() for a in narrow] == ["2026-02-17"]


def test_unit_alternate_resolve_symbol_known_and_unknown() -> None:
    class Recent(_FakeAlpaca):
        def _bars(self, q: httpx.QueryParams) -> httpx.Response:
            if q["symbols"] != "AAA":
                return httpx.Response(200, json={"bars": {}, "next_page_token": None})
            row = {"t": "2026-11-13T05:00:00Z", "o": 1, "h": 2, "l": 1, "c": 1.5, "v": 1}
            return httpx.Response(200, json={"bars": {"AAA": [row]}, "next_page_token": None})

    p = _provider(Recent())
    info = p.resolve_symbol("AAA")
    assert info is not None
    assert (info.symbol, info.type, info.active) == ("AAA", "stock", True)
    assert p.resolve_symbol("ZZZZ9") is None


# ------------------------------------------------------------ retry/errors


def test_unit_alternate_retries_429_then_succeeds_honoring_retry_after() -> None:
    fake, calls = _FakeAlpaca(), {"n": 0}
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return fake(request)

    p = AlternateProvider(KEY, transport=httpx.MockTransport(handler), sleep=sleeps.append)
    assert len(p.daily_bars("AAA", date(2026, 1, 5), date(2026, 1, 9))) == 5
    assert sleeps == [2.0, 2.0]


def test_unit_alternate_5xx_exhausts_retry_budget_as_unavailable() -> None:
    sleeps: list[float] = []
    p = AlternateProvider(
        KEY,
        transport=httpx.MockTransport(lambda r: httpx.Response(503, text="x" * 5000)),
        sleep=sleeps.append,
        jitter=lambda: 1.0,
    )
    with pytest.raises(ProviderUnavailable) as exc:
        p.daily_bars("AAA", date(2026, 1, 5), date(2026, 1, 9))
    assert len(sleeps) == 4  # 5 attempts, a sleep between each
    assert sleeps == [1.0, 2.0, 4.0, 8.0]
    assert len(str(exc.value)) < 200


def test_unit_alternate_429_exhausted_raises_rate_limited_with_retry_after() -> None:
    p = _provider(lambda r: httpx.Response(429, headers={"Retry-After": "7"}))
    with pytest.raises(ProviderRateLimited) as exc:
        p.daily_bars("AAA", date(2026, 1, 5), date(2026, 1, 9))
    assert exc.value.retry_after == 7.0


def test_unit_alternate_transport_error_is_unavailable_and_message_has_no_url() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot reach {request.url}")

    with pytest.raises(ProviderUnavailable) as exc:
        _provider(boom).daily_bars("AAA", date(2026, 1, 5), date(2026, 1, 9))
    assert "http" not in str(exc.value)
    assert SECRET not in str(exc.value)


@pytest.mark.parametrize("code", [401, 403])
def test_unit_alternate_vendor_key_rejection_is_unconfigured(code: int) -> None:
    p = _provider(lambda r: httpx.Response(code, json={"message": "forbidden"}))
    with pytest.raises(ProviderUnconfigured):
        p.daily_bars("AAA", date(2026, 1, 5), date(2026, 1, 9))
    assert p.status().health == "unconfigured"


@pytest.mark.parametrize(
    "payload",
    [
        {"bars": {"AAA": [{"t": "2026-01-05T05:00:00Z", "o": 5, "h": 4, "l": 3, "c": 4, "v": 1}]}},
        {"bars": {"AAA": [{"t": "2026-01-05T05:00:00Z", "o": 1, "h": 2, "l": 1, "c": 1, "v": -1}]}},
        {"bars": {"AAA": [{"t": "2026-01-05T05:00:00Z", "o": 1, "h": 2, "l": 1, "c": 1}]}},
        {"bars": {"AAA": [{"t": "not-a-date", "o": 1, "h": 2, "l": 1, "c": 1, "v": 1}]}},
        {"bars": {"AAA": [{"t": "2026-01-05T05:00:00", "o": 1, "h": 2, "l": 1, "c": 1, "v": 1}]}},
        {"bars": {"AAA": "nope"}},
        {"bars": [1]},
    ],
)
def test_unit_alternate_malformed_or_invalid_payload_is_data_error(payload: dict[str, Any]) -> None:
    p = _provider(lambda r: httpx.Response(200, json=payload))
    with pytest.raises(ProviderDataError):
        p.daily_bars("AAA", date(2026, 1, 1), date(2026, 1, 31))


def test_unit_alternate_non_json_and_client_error_are_data_errors() -> None:
    with pytest.raises(ProviderDataError):
        _provider(lambda r: httpx.Response(200, text="<html>")).daily_bars(
            "AAA", date(2026, 1, 1), date(2026, 1, 31)
        )
    with pytest.raises(ProviderDataError):
        _provider(lambda r: httpx.Response(422, text="bad")).daily_bars(
            "AAA", date(2026, 1, 1), date(2026, 1, 31)
        )


def test_unit_alternate_status_degraded_unreachable_and_ok() -> None:
    assert _provider(lambda r: httpx.Response(429)).status().health == "degraded"
    assert _provider(lambda r: httpx.Response(500)).status().health == "unreachable"
    assert _provider(lambda r: httpx.Response(200, text="x")).status().health == "degraded"
    ok = _provider(_FakeAlpaca()).status()
    assert (ok.name, ok.health, ok.detail) == ("alternate", "ok", None)


# ----------------------------------------------------------- secrets/config


@pytest.mark.parametrize("key", ["", "   ", "onlykeyid", ":secret", "keyid:"])
def test_unit_alternate_missing_or_malformed_key_reports_unconfigured_without_network(
    key: str,
) -> None:
    fake = _FakeAlpaca()
    p = _provider(fake, key=key)
    status = p.status()
    assert (status.health, status.name) == ("unconfigured", "alternate")
    with pytest.raises(ProviderUnconfigured):
        p.daily_bars("AAA", date(2026, 1, 5), date(2026, 1, 9))
    with pytest.raises(ProviderUnconfigured):
        p.corporate_actions("AAA", date(2026, 1, 5), date(2026, 1, 9))
    assert fake.requests == []


def test_unit_alternate_key_never_leaks_into_repr_status_errors_or_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    texts: list[str] = []
    p = _provider(lambda r: httpx.Response(401, json={"message": SECRET}))
    texts.append(repr(p))
    texts.append(repr(p.status()))
    for call in (
        lambda: p.daily_bars("AAA", date(2026, 1, 5), date(2026, 1, 9)),
        lambda: p.corporate_actions("AAA", date(2026, 1, 5), date(2026, 1, 9)),
    ):
        with pytest.raises(ProviderUnconfigured) as exc:
            call()
        texts.append(str(exc.value))
        texts.append(repr(exc.value))
    texts.append(caplog.text)
    joined = "\n".join(texts)
    assert SECRET not in joined
    assert "PKTESTKEYID" not in joined


def test_unit_alternate_bad_base_url_scheme_is_config_error() -> None:
    with pytest.raises(ConfigError):
        AlternateProvider(KEY, "file:///etc/passwd")


# ----------------------------------------------------------------- registry


@pytest.fixture
def _restore_tables() -> Iterator[None]:
    market, fundamentals = dict(registry._MARKET), dict(registry._FUNDAMENTALS)
    yield
    registry._MARKET.clear()
    registry._MARKET.update(market)
    registry._FUNDAMENTALS.clear()
    registry._FUNDAMENTALS.update(fundamentals)


def test_unit_alternate_registry_env_switch_selects_adapter_with_no_code_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERTRENDS_ENV", "ci")
    monkeypatch.setenv("SUPERTRENDS_ALTERNATE_API_KEY", KEY)
    monkeypatch.setenv("SUPERTRENDS_ALTERNATE_BASE_URL", "https://data.example.test")
    monkeypatch.setenv("SUPERTRENDS_MARKET_PROVIDER", "alternate")
    provider = registry.market_provider(load_settings())
    assert isinstance(provider, AlternateProvider)
    assert provider.name == "alternate"
    assert SECRET not in repr(provider)

    monkeypatch.setenv("SUPERTRENDS_MARKET_PROVIDER", "fixture")
    # Before S1-T03 merges the fixture module is missing and the registry says so.
    has_fixture = importlib.util.find_spec("supertrends.data.providers.fixture") is not None
    if has_fixture:
        other = registry.market_provider(load_settings())
        assert not isinstance(other, AlternateProvider)
        assert other.name == "fixture"
    else:
        with pytest.raises(ConfigError, match="no implementation yet"):
            registry.market_provider(load_settings())


def test_unit_alternate_registry_without_key_builds_provider_that_reports_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERTRENDS_ENV", "ci")
    monkeypatch.delenv("SUPERTRENDS_ALTERNATE_API_KEY", raising=False)
    monkeypatch.setenv("SUPERTRENDS_MARKET_PROVIDER", "alternate")
    provider = registry.market_provider(load_settings())
    assert provider.status().health == "unconfigured"


@pytest.mark.usefixtures("_restore_tables")
def test_unit_alternate_registry_mixes_alternate_bars_with_other_fundamentals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERTRENDS_ENV", "ci")
    monkeypatch.setenv("SUPERTRENDS_ALTERNATE_API_KEY", KEY)
    monkeypatch.setenv("SUPERTRENDS_MARKET_PROVIDER", "alternate")
    monkeypatch.setenv("SUPERTRENDS_FUNDAMENTALS_PROVIDER", "massive")
    registry.register_fundamentals_provider("massive", lambda s: FakeFundamentals(name="massive"))
    settings = load_settings()
    market = registry.market_provider(settings)
    fundamentals = registry.fundamentals_provider(settings)
    assert market.name == "alternate"
    assert fundamentals.name == "massive"
