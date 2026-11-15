# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Fixture provider: contract suites, determinism, and dataset shape (TS-ING-001, 002, 004)."""

import itertools
import math
from datetime import date

import pytest

from supertrends.data.calendar import last_completed_session
from supertrends.data.providers import registry
from supertrends.data.providers.base import (
    Bar,
    FundamentalsProvider,
    MarketDataProvider,
    validate_bar,
)
from supertrends.data.providers.fixture import (
    FixtureFundamentals,
    FixtureProvider,
    FixtureUniverse,
)
from supertrends.errors import CapabilityNotSupported
from supertrends.settings import Settings
from tests.contract.provider_contract import FundamentalsProviderContract, MarketProviderContract

END = date(2026, 11, 13)
SEED = 20261114
FULL_START = date(2023, 1, 1)


@pytest.fixture(scope="module")
def universe() -> FixtureUniverse:
    return FixtureUniverse(seed=SEED, end_date=END)


@pytest.fixture(scope="module")
def market(universe: FixtureUniverse) -> FixtureProvider:
    return FixtureProvider(universe)


class TestFixtureMarketContract(MarketProviderContract):
    known_symbol = "FXA"
    unknown_symbol = "ZZZZ9"
    start = date(2026, 1, 5)
    end = date(2026, 3, 27)

    @pytest.fixture
    def provider(self, market: FixtureProvider) -> MarketDataProvider:
        return market


class TestFixtureFundamentalsContract(FundamentalsProviderContract):
    known_symbol = "FXA"
    unknown_symbol = "ZZZZ9"
    start = date(2025, 1, 1)
    end = date(2026, 12, 31)

    @pytest.fixture
    def provider(self, universe: FixtureUniverse) -> FundamentalsProvider:
        return FixtureFundamentals(universe)


def _closes(p: FixtureProvider, sym: str) -> list[float]:
    return [b.close for b in p.daily_bars(sym, FULL_START, END)]


def test_unit_fixture_provider_generate_same_seed_identical_bars(market: FixtureProvider) -> None:
    other = FixtureProvider(FixtureUniverse(seed=SEED, end_date=END))
    for sym in ("FXA", "FXC", "SPY"):
        assert market.daily_bars(sym, FULL_START, END) == other.daily_bars(sym, FULL_START, END)
        assert market.intraday_bars(sym, FULL_START, END) == other.intraday_bars(
            sym, FULL_START, END
        )


def test_unit_fixture_provider_different_seed_different_bars(market: FixtureProvider) -> None:
    other = FixtureProvider(FixtureUniverse(seed=SEED + 1, end_date=END))
    assert market.daily_bars("FXA", FULL_START, END) != other.daily_bars("FXA", FULL_START, END)


def test_unit_fixture_provider_values_depend_on_session_index_not_end_date(
    market: FixtureProvider,
) -> None:
    shifted = FixtureProvider(FixtureUniverse(seed=SEED, end_date=date(2026, 10, 30)))
    assert _closes(market, "FXA") == _closes(shifted, "FXA")


def test_unit_fixture_provider_history_sizes(market: FixtureProvider) -> None:
    daily = market.daily_bars("FXA", FULL_START, END)
    assert 750 <= len(daily) <= 760
    assert daily[-1].ts.date() == END
    intraday = market.intraday_bars("FXA", FULL_START, END)
    days = {b.ts.date() for b in intraday}
    assert len(days) == 30
    assert len(intraday) >= 30 * 42  # half-day sessions have 42 five-minute bars
    assert all(b.ts.tzinfo is not None for b in intraday)
    assert min(days) == daily[-30].ts.date()


def test_unit_fixture_provider_universe_and_stand_ins(market: FixtureProvider) -> None:
    symbols = FixtureUniverse.symbols()
    assert symbols[:12] == [f"FX{c}" for c in "ABCDEFGHIJKL"]
    assert "SPY" in symbols
    assert "QQQ" in symbols
    assert len(symbols) == 14
    types = set()
    for s in symbols:
        info = market.resolve_symbol(s)
        assert info is not None
        types.add(info.type)
        assert len(market.daily_bars(s, FULL_START, END)) > 700
    assert types == {"stock", "etf"}


def test_unit_fixture_provider_bars_are_valid(market: FixtureProvider) -> None:
    for s in FixtureUniverse.symbols():
        for b in market.daily_bars(s, FULL_START, END):
            validate_bar(b)
        for b in market.intraday_bars(s, FULL_START, END):
            validate_bar(b)


def test_unit_fixture_provider_intraday_aggregates_to_daily(market: FixtureProvider) -> None:
    daily = {b.ts.date(): b for b in market.daily_bars("FXB", date(2026, 10, 1), END)}
    by_day: dict[date, list[Bar]] = {}
    for b in market.intraday_bars("FXB", date(2026, 10, 1), END):
        by_day.setdefault(b.ts.date(), []).append(b)
    assert by_day
    for day, bars in by_day.items():
        d = daily[day]
        assert bars[0].open == d.open
        assert bars[-1].close == d.close
        assert max(x.high for x in bars) == d.high
        assert min(x.low for x in bars) == d.low
        assert sum(x.volume for x in bars) == d.volume
        steps = {(b2.ts - b1.ts).total_seconds() for b1, b2 in itertools.pairwise(bars)}
        assert steps <= {300.0}


def _stats(closes: list[float]) -> tuple[float, float, float, float]:
    """Net log drift, log range, first-half drift, second-half drift."""
    logs = [math.log(c) for c in closes]
    half = len(logs) // 2
    return (
        logs[-1] - logs[0],
        max(logs) - min(logs),
        logs[half] - logs[0],
        logs[-1] - logs[half],
    )


def test_unit_fixture_provider_dataset_has_trending_ranging_reversing_tickers(
    market: FixtureProvider,
) -> None:
    trend = _stats(_closes(market, "FXA"))
    rng = _stats(_closes(market, "FXB"))
    rev = _stats(_closes(market, "FXC"))
    # Trending: large net drift that is most of the traversed range.
    assert trend[0] > 0.8
    assert trend[0] / trend[1] > 0.8
    # Ranging: little net drift relative to the range, and a bounded range.
    assert abs(rng[0]) < 0.15
    assert abs(rng[0]) / rng[1] < 0.35
    assert rng[1] < 0.8
    # Reversing: the trend sign flips between halves, both legs substantial.
    assert rev[2] > 0.25
    assert rev[3] < -0.25


def test_unit_fixture_provider_split_reported_as_corporate_action(market: FixtureProvider) -> None:
    actions = market.corporate_actions("FXE", FULL_START, END)
    splits = [a for a in actions if a.kind == "split"]
    assert len(splits) == 1
    assert splits[0].ratio == 4.0
    assert FULL_START < splits[0].ex_date < END
    total = sum(
        1
        for s in FixtureUniverse.symbols()
        for a in market.corporate_actions(s, FULL_START, END)
        if a.kind == "split"
    )
    assert total == 1
    # Bars are split adjusted: no 4:1 cliff at the ex-date.
    bars = {b.ts.date(): b for b in market.daily_bars("FXE", FULL_START, END)}
    ex = splits[0].ex_date
    prev = max(d for d in bars if d < ex)
    assert 0.8 < bars[ex].open / bars[prev].close < 1.25


def test_unit_fixture_provider_overnight_gaps_exist(market: FixtureProvider) -> None:
    bars = market.daily_bars("FXD", FULL_START, END)
    gaps = [abs(b.open / a.close - 1) for a, b in itertools.pairwise(bars)]
    assert max(gaps) > 0.02


def test_unit_fixture_provider_capabilities_and_trades(market: FixtureProvider) -> None:
    c = market.capabilities
    assert (c.intraday, c.trades, c.adjusted, c.grouped_daily, c.reference) == (
        True,
        False,
        True,
        True,
        True,
    )
    with pytest.raises(CapabilityNotSupported):
        market.trades("FXA", END)
    assert {b.symbol for b in market.grouped_daily(END)} == set(FixtureUniverse.symbols())
    assert market.grouped_daily(date(2026, 11, 14)) == []  # Saturday


def test_unit_fixture_provider_non_session_dates_have_no_bars(market: FixtureProvider) -> None:
    assert market.daily_bars("FXA", date(2026, 11, 14), date(2026, 11, 15)) == []
    assert market.intraday_bars("FXA", date(2026, 11, 14), date(2026, 11, 15)) == []


def test_unit_fixture_provider_etf_has_no_financials_and_stocks_do(
    universe: FixtureUniverse,
) -> None:
    f = FixtureFundamentals(universe)
    assert f.quarterly_financials("SPY", FULL_START) == []
    assert f.quarterly_financials("FXK", FULL_START) == []
    rows = f.quarterly_financials("FXA", FULL_START)
    assert len(rows) >= 10
    for r in rows:
        assert (r.known_at.date() - r.period_end).days == 30
        assert set(r.metrics) == {
            "revenue",
            "eps_diluted",
            "gross_margin",
            "operating_margin",
            "fcf",
            "net_debt",
            "shares",
        }
    assert f.supports_forward_estimates is False
    assert f.forward_estimates("FXA") == []
    assert rows == f.quarterly_financials("FXA", FULL_START)


def test_unit_fixture_provider_earnings_in_three_sessions_for_event_risk_ticker(
    universe: FixtureUniverse,
) -> None:
    f = FixtureFundamentals(universe)
    rows = f.earnings_dates("FXH", END, date(2026, 12, 31))
    assert rows
    assert rows[0].date == date(2026, 11, 18)  # three sessions after 2026-11-13
    assert f.earnings_dates("SPY", FULL_START, date(2026, 12, 31)) == []


def test_unit_fixture_provider_unknown_symbol_none_unless_permissive(
    universe: FixtureUniverse,
) -> None:
    strict = FixtureProvider(universe)
    assert strict.resolve_symbol("AAPL") is None
    assert strict.daily_bars("AAPL", FULL_START, END) == []
    permissive = FixtureUniverse(seed=SEED, end_date=END, permissive=True)
    loose = FixtureProvider(permissive)
    assert loose.resolve_symbol("AAPL") is not None
    bars = loose.daily_bars("AAPL", FULL_START, END)
    assert len(bars) > 700
    again = FixtureProvider(FixtureUniverse(seed=SEED, end_date=END, permissive=True))
    assert bars == again.daily_bars("AAPL", FULL_START, END)
    assert bars != loose.daily_bars("MSFT", FULL_START, END)
    assert loose.resolve_symbol("not a symbol!") is None
    assert loose.resolve_symbol("") is None
    assert FixtureFundamentals(permissive).quarterly_financials("AAPL", FULL_START)


def test_unit_fixture_provider_status_and_call_log(market: FixtureProvider) -> None:
    s = market.status()
    assert (s.name, s.health) == ("fixture", "ok")
    before = len(market.calls)
    market.daily_bars("FXA", END, END)
    assert market.calls[-1] == ("daily_bars", "FXA")
    assert len(market.calls) == before + 1


def test_unit_fixture_provider_registry_builds_from_settings() -> None:
    s = Settings(fixture_end_date="2026-11-13")
    m = registry.market_provider(s)
    f = registry.fundamentals_provider(s)
    assert isinstance(m, FixtureProvider)
    assert isinstance(f, FixtureFundamentals)
    assert m.daily_bars("FXA", END, END)[0].ts.date() == END


def test_unit_fixture_provider_default_end_is_last_completed_session() -> None:
    m = FixtureProvider.from_settings(Settings())
    assert m.universe.end_date == last_completed_session()
