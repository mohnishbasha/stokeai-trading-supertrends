# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Shared provider contract suite (ARCHITECTURE section 7; TEST_PLAN TS-ING-004 to TS-ING-006).

Any provider implementation runs this suite by subclassing `MarketProviderContract` (market
data) or `FundamentalsProviderContract` (fundamentals) in a test module that pytest collects
(for example `tests/unit/test_provider_contract_fixture.py`), and overriding:

* the `provider` fixture, returning a ready provider (recorded fixtures behind an
  `httpx.MockTransport` for vendor adapters, never the network);
* class attributes `known_symbol`, `unknown_symbol`, `start`, and `end`, where the symbol has
  data across [start, end], so the checks have rows to inspect.

Plug-in pattern for S1-T03 (fixture), S1-T04 (Massive), and S1-T05 (alternate):

    class TestMassiveMarketContract(MarketProviderContract):
        known_symbol = "AAPL"
        start, end = date(2026, 1, 5), date(2026, 3, 27)

        @pytest.fixture
        def provider(self) -> MarketDataProvider:
            return build_massive_with_recorded_transport()

The base classes are not named `Test*`, so pytest only collects concrete subclasses.
"""

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import ClassVar, get_args

import pytest

from supertrends.data.providers.base import (
    Bar,
    CorporateAction,
    EarningsDate,
    ForwardEstimate,
    FundamentalsProvider,
    MarketDataProvider,
    ProviderCapabilities,
    ProviderHealth,
    ProviderStatus,
    QuarterlyFinancials,
    SymbolInfo,
)
from supertrends.errors import CapabilityNotSupported


def _assert_bars(bars: Sequence[Bar], symbol: str, start: date, end: date, *, daily: bool) -> None:
    ts = [b.ts for b in bars]
    for b in bars:
        assert isinstance(b, Bar)
        assert b.symbol == symbol
        assert isinstance(b.ts, datetime)
        assert isinstance(b.volume, int)
        assert b.volume >= 0
        assert b.low <= min(b.open, b.close)
        assert b.high >= max(b.open, b.close)
        assert b.low > 0
        assert start <= b.ts.date() <= end
        if not daily:
            assert b.ts.tzinfo is not None, "intraday bar start must be timezone-aware (UTC)"
    assert ts == sorted(ts), "bars must be sorted by ts ascending"
    assert len(set(ts)) == len(ts), "bars must not contain duplicate ts"


class MarketProviderContract:
    """Contract for any MarketDataProvider. Override `provider` and the class attributes."""

    known_symbol: ClassVar[str] = "AAA"
    unknown_symbol: ClassVar[str] = "ZZZZ9"
    start: ClassVar[date] = date(2026, 1, 5)
    end: ClassVar[date] = date(2026, 3, 27)

    @pytest.fixture
    def provider(self) -> MarketDataProvider:
        raise NotImplementedError("override the provider fixture")

    @pytest.fixture
    def caps(self, provider: MarketDataProvider) -> ProviderCapabilities:
        return provider.capabilities

    def test_contract_market_provider_satisfies_protocol(
        self, provider: MarketDataProvider
    ) -> None:
        assert isinstance(provider, MarketDataProvider)
        assert isinstance(provider.name, str)
        assert provider.name
        assert isinstance(provider.capabilities, ProviderCapabilities)
        for flag in ("intraday", "trades", "adjusted", "grouped_daily", "reference"):
            assert isinstance(getattr(provider.capabilities, flag), bool)

    def test_contract_daily_bars_typed_sorted_unique_sane(
        self, provider: MarketDataProvider
    ) -> None:
        bars = provider.daily_bars(self.known_symbol, self.start, self.end)
        assert len(bars) > 0
        _assert_bars(bars, self.known_symbol, self.start, self.end, daily=True)

    def test_contract_daily_bars_respect_narrower_range(self, provider: MarketDataProvider) -> None:
        full = provider.daily_bars(self.known_symbol, self.start, self.end)
        lo = self.start + timedelta(days=14)
        hi = self.end - timedelta(days=14)
        sub = provider.daily_bars(self.known_symbol, lo, hi)
        _assert_bars(sub, self.known_symbol, lo, hi, daily=True)
        assert 0 < len(sub) < len(full)

    def test_contract_daily_bars_inclusive_single_day(self, provider: MarketDataProvider) -> None:
        full = provider.daily_bars(self.known_symbol, self.start, self.end)
        day = full[len(full) // 2].ts.date()
        one = provider.daily_bars(self.known_symbol, day, day)
        assert [b.ts.date() for b in one] == [day]

    def test_contract_daily_bars_empty_range_is_valid_empty(
        self, provider: MarketDataProvider
    ) -> None:
        # A range far before any data: empty is valid, not an error.
        assert (
            list(provider.daily_bars(self.known_symbol, date(1990, 1, 1), date(1990, 1, 7))) == []
        )

    def test_contract_unknown_symbol_resolves_to_none_and_has_no_bars(
        self, provider: MarketDataProvider
    ) -> None:
        # ARCHITECTURE 7.3: unknown is not an error; resolve_symbol gives None, series are empty.
        assert provider.resolve_symbol(self.unknown_symbol) is None
        assert list(provider.daily_bars(self.unknown_symbol, self.start, self.end)) == []
        assert list(provider.corporate_actions(self.unknown_symbol, self.start, self.end)) == []

    def test_contract_resolve_symbol_known_returns_symbol_info(
        self, provider: MarketDataProvider
    ) -> None:
        info = provider.resolve_symbol(self.known_symbol)
        assert isinstance(info, SymbolInfo)
        assert info.symbol == self.known_symbol
        assert info.type in {"stock", "etf", "index", "crypto"}

    def test_contract_intraday_matches_capability_flag(
        self, provider: MarketDataProvider, caps: ProviderCapabilities
    ) -> None:
        if caps.intraday:
            bars = provider.intraday_bars(self.known_symbol, self.start, self.end)
            _assert_bars(bars, self.known_symbol, self.start, self.end, daily=False)
        else:
            with pytest.raises(CapabilityNotSupported):
                provider.intraday_bars(self.known_symbol, self.start, self.end)

    def test_contract_grouped_daily_matches_capability_flag(
        self, provider: MarketDataProvider, caps: ProviderCapabilities
    ) -> None:
        day = provider.daily_bars(self.known_symbol, self.start, self.end)[0].ts.date()
        if caps.grouped_daily:
            bars = provider.grouped_daily(day)
            ts = [(b.symbol, b.ts) for b in bars]
            assert len(set(ts)) == len(ts)
            for b in bars:
                assert isinstance(b, Bar)
                assert b.ts.date() == day
                assert b.low <= min(b.open, b.close)
                assert b.high >= max(b.open, b.close)
                assert b.volume >= 0
        else:
            with pytest.raises(CapabilityNotSupported):
                provider.grouped_daily(day)

    def test_contract_trades_matches_capability_flag(
        self, provider: MarketDataProvider, caps: ProviderCapabilities
    ) -> None:
        day = self.start
        if caps.trades:
            assert isinstance(provider.trades(self.known_symbol, day), Sequence)
        else:
            with pytest.raises(CapabilityNotSupported):
                provider.trades(self.known_symbol, day)

    def test_contract_corporate_actions_typed_sorted_in_range(
        self, provider: MarketDataProvider
    ) -> None:
        actions = provider.corporate_actions(self.known_symbol, self.start, self.end)
        dates = [a.ex_date for a in actions]
        assert dates == sorted(dates)
        for a in actions:
            assert isinstance(a, CorporateAction)
            assert a.symbol == self.known_symbol
            assert self.start <= a.ex_date <= self.end
            if a.kind == "split":
                assert a.ratio is not None
                assert a.ratio > 0
            else:
                assert a.kind == "dividend"
                assert a.amount is not None
                assert a.amount >= 0
        keys = [(a.ex_date, a.kind) for a in actions]
        assert len(set(keys)) == len(keys)

    def test_contract_status_is_typed_and_names_provider(
        self, provider: MarketDataProvider
    ) -> None:
        status = provider.status()
        assert isinstance(status, ProviderStatus)
        assert status.name == provider.name
        assert status.health in get_args(ProviderHealth)


class FundamentalsProviderContract:
    """Contract for any FundamentalsProvider. Override `provider` and the class attributes."""

    known_symbol: ClassVar[str] = "AAA"
    unknown_symbol: ClassVar[str] = "ZZZZ9"
    start: ClassVar[date] = date(2025, 1, 1)
    end: ClassVar[date] = date(2026, 12, 31)

    @pytest.fixture
    def provider(self) -> FundamentalsProvider:
        raise NotImplementedError("override the provider fixture")

    def test_contract_fundamentals_provider_satisfies_protocol(
        self, provider: FundamentalsProvider
    ) -> None:
        assert isinstance(provider, FundamentalsProvider)
        assert provider.name
        assert isinstance(provider.supports_forward_estimates, bool)

    def test_contract_quarterly_financials_typed_sorted_unique_since_bound(
        self, provider: FundamentalsProvider
    ) -> None:
        rows = provider.quarterly_financials(self.known_symbol, self.start)
        assert len(rows) > 0
        for r in rows:
            assert isinstance(r, QuarterlyFinancials)
            assert r.symbol == self.known_symbol
            assert r.period_end >= self.start
            assert r.known_at.tzinfo is not None, "known_at must be timezone-aware"
            assert r.known_at.date() >= r.period_end, "known_at cannot precede the period end"
            assert all(v is None or isinstance(v, float) for v in r.metrics.values())
        ends = [r.period_end for r in rows]
        assert ends == sorted(ends)
        assert len(set(ends)) == len(ends)

    def test_contract_quarterly_financials_unknown_symbol_is_empty(
        self, provider: FundamentalsProvider
    ) -> None:
        assert list(provider.quarterly_financials(self.unknown_symbol, self.start)) == []

    def test_contract_forward_estimates_match_capability_flag(
        self, provider: FundamentalsProvider
    ) -> None:
        if provider.supports_forward_estimates:
            for e in provider.forward_estimates(self.known_symbol):
                assert isinstance(e, ForwardEstimate)
                assert e.symbol == self.known_symbol
        else:
            try:
                result = provider.forward_estimates(self.known_symbol)
            except CapabilityNotSupported:
                return
            assert list(result) == []

    def test_contract_earnings_dates_typed_sorted_unique_in_range(
        self, provider: FundamentalsProvider
    ) -> None:
        rows = provider.earnings_dates(self.known_symbol, self.start, self.end)
        dates = [r.date for r in rows]
        for r in rows:
            assert isinstance(r, EarningsDate)
            assert r.symbol == self.known_symbol
            assert self.start <= r.date <= self.end
            assert isinstance(r.confirmed, bool)
        assert dates == sorted(dates)
        assert len(set(dates)) == len(dates)

    def test_contract_earnings_dates_unknown_symbol_is_empty(
        self, provider: FundamentalsProvider
    ) -> None:
        assert list(provider.earnings_dates(self.unknown_symbol, self.start, self.end)) == []

    def test_contract_fundamentals_status_is_typed_and_names_provider(
        self, provider: FundamentalsProvider
    ) -> None:
        status = provider.status()
        assert isinstance(status, ProviderStatus)
        assert status.name == provider.name
        assert status.health in get_args(ProviderHealth)
