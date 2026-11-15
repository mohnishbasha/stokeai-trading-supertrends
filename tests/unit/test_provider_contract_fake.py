# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Fake providers pass the shared provider contract suite (TS-ING-041 to TS-ING-043)."""

from collections.abc import Sequence
from datetime import date, datetime

import pytest

from supertrends.data.providers.base import Bar, MarketDataProvider, validate_bar
from supertrends.errors import ProviderDataError
from tests.contract.fakes import FakeFundamentals, FakeProvider
from tests.contract.provider_contract import FundamentalsProviderContract, MarketProviderContract


class TestFakeMarketContract(MarketProviderContract):
    known_symbol = "AAA"
    start = date(2026, 1, 5)
    end = date(2026, 3, 27)

    @pytest.fixture
    def provider(self) -> MarketDataProvider:
        return FakeProvider()


class TestFakeMarketNoIntradayContract(MarketProviderContract):
    """Capability flags off: unsupported methods raise CapabilityNotSupported."""

    @pytest.fixture
    def provider(self) -> MarketDataProvider:
        return FakeProvider(intraday=False, grouped_daily=False)


class TestFakeFundamentalsContract(FundamentalsProviderContract):
    @pytest.fixture
    def provider(self) -> FakeFundamentals:
        return FakeFundamentals()


class TestFakeFundamentalsNoForwardContract(FundamentalsProviderContract):
    @pytest.fixture
    def provider(self) -> FakeFundamentals:
        return FakeFundamentals(forward_estimates=False)


class _Unsorted(FakeProvider):
    def daily_bars(self, symbol: str, start: date, end: date) -> Sequence[Bar]:
        return list(reversed(super().daily_bars(symbol, start, end)))


class _LeaksRange(FakeProvider):
    def daily_bars(self, symbol: str, start: date, end: date) -> Sequence[Bar]:
        return super().daily_bars(symbol, date(2026, 1, 1), date(2026, 6, 30))


class _NoCapabilityError(FakeProvider):
    def __init__(self) -> None:
        super().__init__(intraday=False)

    def intraday_bars(self, symbol: str, start: date, end: date, minutes: int = 5) -> Sequence[Bar]:
        return []


@pytest.mark.parametrize(
    ("bad", "check"),
    [
        (_Unsorted, "test_contract_daily_bars_typed_sorted_unique_sane"),
        (_LeaksRange, "test_contract_daily_bars_respect_narrower_range"),
        (_NoCapabilityError, "test_contract_intraday_matches_capability_flag"),
    ],
)
def test_contract_suite_detects_violating_provider(bad: type[FakeProvider], check: str) -> None:
    suite = MarketProviderContract()
    provider = bad()
    args = (provider, provider.capabilities) if "capability" in check else (provider,)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        getattr(suite, check)(*args)


def test_validate_bar_rejects_invariant_violations() -> None:
    ts = datetime(2026, 1, 5)
    validate_bar(Bar("A", ts, 1.0, 2.0, 0.5, 1.5, 10))
    for bad in (
        Bar("A", ts, 1.0, 0.9, 0.5, 1.5, 10),
        Bar("A", ts, 1.0, 2.0, 1.2, 1.5, 10),
        Bar("A", ts, 1.0, 2.0, 0.5, 1.5, -1),
        Bar("A", ts, float("nan"), 2.0, 0.5, 1.5, 1),
    ):
        with pytest.raises(ProviderDataError):
            validate_bar(bad)
