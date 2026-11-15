# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Provider result types and Protocols (ARCHITECTURE sections 7.1 and 7.2).

Return contracts: sequences are sorted by time ascending, contain no duplicates, and contain
only rows within [start, end] inclusive. Empty results are valid. Adapters validate rows with
`validate_bar`; a violating row raises ProviderDataError. Calling a method whose capability
flag is false raises CapabilityNotSupported without network I/O.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol, runtime_checkable

from supertrends.errors import ProviderDataError


@dataclass(frozen=True)
class ProviderCapabilities:
    """What a market data provider (and plan) can do."""

    intraday: bool  # 5-minute bars available on this plan
    trades: bool  # tick trades available (reserved for tick-rule flow, ADR-010)
    adjusted: bool  # bars are split and dividend adjusted by the vendor
    grouped_daily: bool  # whole-market daily bars in one call
    reference: bool  # symbol resolution and names


@dataclass(frozen=True)
class Bar:
    """One OHLCV bar."""

    symbol: str
    ts: datetime  # session date at 00:00 America/New_York for daily, bar start (UTC) for intraday
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None = None


@dataclass(frozen=True)
class CorporateAction:
    """A split or dividend."""

    symbol: str
    ex_date: date
    kind: Literal["split", "dividend"]
    ratio: float | None  # split: new shares per old share
    amount: float | None  # dividend cash amount


@dataclass(frozen=True)
class SymbolInfo:
    """Reference data for a symbol."""

    symbol: str
    name: str | None
    type: Literal["stock", "etf", "index", "crypto"]
    active: bool


@dataclass(frozen=True)
class QuarterlyFinancials:
    """One fiscal quarter of reported financials."""

    symbol: str
    period_end: date
    known_at: datetime  # point-in-time availability (filing date or vendor timestamp)
    # revenue, eps_diluted, gross_margin, operating_margin, fcf, net_debt, shares
    metrics: dict[str, float | None]


@dataclass(frozen=True)
class ForwardEstimate:
    """Consensus forward estimates as of a timestamp."""

    symbol: str
    as_of: datetime
    eps_next_12m: float | None
    revenue_next_12m: float | None


@dataclass(frozen=True)
class EarningsDate:
    """A scheduled or reported earnings date."""

    symbol: str
    date: date
    confirmed: bool


ProviderHealth = Literal["ok", "degraded", "unconfigured", "unreachable"]


@dataclass(frozen=True)
class ProviderStatus:
    """Provider health for /readyz and the status page."""

    name: str
    health: ProviderHealth
    detail: str | None  # never contains a secret


@runtime_checkable
class MarketDataProvider(Protocol):
    """Daily and intraday bars, corporate actions, and symbol reference data."""

    name: str
    capabilities: ProviderCapabilities

    def daily_bars(self, symbol: str, start: date, end: date) -> Sequence[Bar]: ...

    def grouped_daily(self, session: date) -> Sequence[Bar]:
        """Requires capabilities.grouped_daily."""
        ...

    def intraday_bars(
        self, symbol: str, start: date, end: date, minutes: Literal[5] = 5
    ) -> Sequence[Bar]:
        """Requires capabilities.intraday."""
        ...

    def corporate_actions(
        self, symbol: str, start: date, end: date
    ) -> Sequence[CorporateAction]: ...

    def resolve_symbol(self, symbol: str) -> SymbolInfo | None:
        """None when the symbol is unknown."""
        ...

    def trades(self, symbol: str, session: date) -> Sequence[object]:
        """Requires capabilities.trades. Unused in v1."""
        ...

    def status(self) -> ProviderStatus: ...


@runtime_checkable
class FundamentalsProvider(Protocol):
    """Quarterly financials, forward estimates, and earnings dates."""

    name: str
    supports_forward_estimates: bool

    def quarterly_financials(self, symbol: str, since: date) -> Sequence[QuarterlyFinancials]: ...

    def forward_estimates(self, symbol: str) -> Sequence[ForwardEstimate]:
        """Empty, or CapabilityNotSupported when supports_forward_estimates is false."""
        ...

    def earnings_dates(self, symbol: str, start: date, end: date) -> Sequence[EarningsDate]: ...

    def status(self) -> ProviderStatus: ...


def validate_bar(bar: Bar) -> Bar:
    """Return the bar when its OHLCV invariants hold, else raise ProviderDataError."""
    prices = (bar.open, bar.high, bar.low, bar.close)
    if not all(math.isfinite(p) for p in prices):
        msg = f"non-finite price for {bar.symbol} at {bar.ts.isoformat()}"
        raise ProviderDataError(msg)
    if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
        msg = f"OHLC invariant violated for {bar.symbol} at {bar.ts.isoformat()}"
        raise ProviderDataError(msg)
    if bar.volume < 0:
        msg = f"negative volume for {bar.symbol} at {bar.ts.isoformat()}"
        raise ProviderDataError(msg)
    return bar
