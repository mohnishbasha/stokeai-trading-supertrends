# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Massive adapter passes the shared provider contract suite on recorded fixtures (TS-ING-005)."""

from datetime import date

import pytest

from supertrends.data.providers.base import FundamentalsProvider, MarketDataProvider
from supertrends.data.providers.massive import MassiveFundamentals, MassiveProvider
from supertrends.errors import CapabilityNotSupported
from tests.contract.massive_support import make_client
from tests.contract.provider_contract import FundamentalsProviderContract, MarketProviderContract


class TestMassiveMarketContract(MarketProviderContract):
    known_symbol = "AAA"
    start = date(2026, 1, 5)
    end = date(2026, 3, 27)

    @pytest.fixture
    def provider(self) -> MarketDataProvider:
        return MassiveProvider(make_client()[0])


class TestMassiveFundamentalsContract(FundamentalsProviderContract):
    known_symbol = "AAA"
    start = date(2025, 1, 1)
    end = date(2026, 12, 31)

    @pytest.fixture
    def provider(self) -> FundamentalsProvider:
        return MassiveFundamentals(make_client()[0])

    def test_contract_earnings_dates_typed_sorted_unique_in_range(
        self, provider: FundamentalsProvider
    ) -> None:
        # Massive has no earnings calendar endpoint (ARCHITECTURE 7.6): documented capability gap.
        with pytest.raises(CapabilityNotSupported):
            provider.earnings_dates(self.known_symbol, self.start, self.end)

    def test_contract_earnings_dates_unknown_symbol_is_empty(
        self, provider: FundamentalsProvider
    ) -> None:
        with pytest.raises(CapabilityNotSupported):
            provider.earnings_dates(self.unknown_symbol, self.start, self.end)
