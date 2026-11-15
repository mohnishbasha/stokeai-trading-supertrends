# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""In-memory provider doubles that satisfy the provider Protocols and the contract suite."""

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

from supertrends.data.providers.base import (
    Bar,
    CorporateAction,
    EarningsDate,
    ForwardEstimate,
    ProviderCapabilities,
    ProviderStatus,
    QuarterlyFinancials,
    SymbolInfo,
    validate_bar,
)
from supertrends.errors import CapabilityNotSupported

KNOWN = "AAA"
DATA_START = date(2026, 1, 1)
DATA_END = date(2026, 6, 30)


def _weekdays(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _bar(symbol: str, ts: datetime, i: int) -> Bar:
    base = 100.0 + i * 0.1
    return validate_bar(
        Bar(symbol, ts, base, base + 1.5, base - 1.0, base + 0.5, 1_000_000 + i, base + 0.2)
    )


class FakeProvider:
    """Deterministic in-memory MarketDataProvider with configurable capabilities."""

    def __init__(
        self,
        *,
        intraday: bool = True,
        trades: bool = False,
        grouped_daily: bool = True,
        name: str = "fake",
    ) -> None:
        self.name = name
        self.capabilities = ProviderCapabilities(
            intraday=intraday,
            trades=trades,
            adjusted=True,
            grouped_daily=grouped_daily,
            reference=True,
        )

    def daily_bars(self, symbol: str, start: date, end: date) -> Sequence[Bar]:
        if symbol != KNOWN:
            return []
        days = _weekdays(DATA_START, DATA_END)
        return [
            _bar(symbol, datetime.combine(d, time.min), i)
            for i, d in enumerate(days)
            if start <= d <= end
        ]

    def grouped_daily(self, session: date) -> Sequence[Bar]:
        if not self.capabilities.grouped_daily:
            raise CapabilityNotSupported("grouped_daily is not supported by this provider")
        return self.daily_bars(KNOWN, session, session)

    def intraday_bars(
        self, symbol: str, start: date, end: date, minutes: Literal[5] = 5
    ) -> Sequence[Bar]:
        if not self.capabilities.intraday:
            raise CapabilityNotSupported("intraday bars are not supported by this provider")
        if symbol != KNOWN:
            return []
        out: list[Bar] = []
        for d in _weekdays(max(start, DATA_START), min(end, DATA_END)):
            open_utc = datetime.combine(d, time(14, 30), tzinfo=UTC)
            out.extend(_bar(symbol, open_utc + timedelta(minutes=5 * k), k) for k in range(12))
        return out

    def corporate_actions(self, symbol: str, start: date, end: date) -> Sequence[CorporateAction]:
        if symbol != KNOWN:
            return []
        actions = [
            CorporateAction(symbol, date(2026, 2, 13), "dividend", None, 0.25),
            CorporateAction(symbol, date(2026, 4, 1), "split", 4.0, None),
        ]
        return [a for a in actions if start <= a.ex_date <= end]

    def resolve_symbol(self, symbol: str) -> SymbolInfo | None:
        if symbol != KNOWN:
            return None
        return SymbolInfo(symbol, "Fake Corp", "stock", True)

    def trades(self, symbol: str, session: date) -> Sequence[object]:
        if not self.capabilities.trades:
            raise CapabilityNotSupported("trades are not supported by this provider")
        return []

    def status(self) -> ProviderStatus:
        return ProviderStatus(self.name, "ok", None)


class FakeFundamentals:
    """Deterministic in-memory FundamentalsProvider."""

    def __init__(self, *, forward_estimates: bool = True, name: str = "fake-fundamentals") -> None:
        self.name = name
        self.supports_forward_estimates = forward_estimates

    def quarterly_financials(self, symbol: str, since: date) -> Sequence[QuarterlyFinancials]:
        if symbol != KNOWN:
            return []
        ends = [date(2025, 3, 31), date(2025, 6, 30), date(2025, 9, 30), date(2025, 12, 31)]
        return [
            QuarterlyFinancials(
                symbol,
                e,
                datetime.combine(e + timedelta(days=30), time.min, tzinfo=UTC),
                {"revenue": 1.0e9 + i, "eps_diluted": 1.25 + i / 10, "fcf": None},
            )
            for i, e in enumerate(ends)
            if e >= since
        ]

    def forward_estimates(self, symbol: str) -> Sequence[ForwardEstimate]:
        if not self.supports_forward_estimates:
            raise CapabilityNotSupported("forward estimates are not supported")
        if symbol != KNOWN:
            return []
        return [ForwardEstimate(symbol, datetime(2026, 1, 2, tzinfo=UTC), 5.5, 4.2e9)]

    def earnings_dates(self, symbol: str, start: date, end: date) -> Sequence[EarningsDate]:
        if symbol != KNOWN:
            return []
        rows = [
            EarningsDate(symbol, date(2026, 2, 5), True),
            EarningsDate(symbol, date(2026, 5, 7), False),
        ]
        return [r for r in rows if start <= r.date <= end]

    def status(self) -> ProviderStatus:
        return ProviderStatus(self.name, "ok", None)
