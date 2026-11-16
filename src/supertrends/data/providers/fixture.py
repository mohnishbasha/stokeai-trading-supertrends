# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
# ruff: noqa: S311 (seeded pseudo-random data is the point; nothing here is security sensitive)
"""Deterministic synthetic provider (ARCHITECTURE section 7.5, ADR-028).

Generates 3 years of daily bars and the latest 30 sessions of 5-minute bars for 12 synthetic
tickers (`FXA` to `FXL`) plus `SPY` and `QQQ` stand-ins, on XNYS sessions, with seeded
geometric Brownian motion, regime switches, overnight gaps, one 4:1 split, and volume
patterns. No network I/O and no vendor data, ever.

Determinism: every random draw comes from `random.Random` seeded with a string built from the
seed, the symbol, and the session index counted back from the end date (0 is the end date).
Values therefore depend only on the seed and that index, so shapes are identical for any end
date (only half-day sessions in the intraday window depend on the calendar, by truncation).

By construction (asserted in tests/unit/test_provider_fixture.py): `FXA` trends up, `FXB`
ranges (mean reverting), `FXC` reverses (up then down), `FXD` trends down. `FXF` and `FXG`
share most of their shocks and regimes (correlated pair), `FXH` reports earnings in three
sessions, `FXE` has the 4:1 split. Bars are split adjusted (capability `adjusted`), so the
split shows up only as a corporate action. Daily bars of the intraday window are the exact
aggregate of the 5-minute bars.
"""

import re
from bisect import bisect_left, bisect_right
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from hashlib import sha256
from math import copysign, exp, log, sqrt
from random import Random
from typing import Literal
from zoneinfo import ZoneInfo

from supertrends.data.calendar import last_completed_session, session_bounds, sessions_between
from supertrends.data.providers.base import (
    Bar,
    CorporateAction,
    EarningsDate,
    ForwardEstimate,
    ProviderCapabilities,
    ProviderStatus,
    QuarterlyFinancials,
    SymbolInfo,
)
from supertrends.errors import CapabilityNotSupported
from supertrends.settings import Settings

DAILY_SESSIONS = 756  # 3 years
INTRADAY_SESSIONS = 30
FULL_DAY_BARS = 78  # 6.5 hours of 5-minute bars
SPLIT_RATIO = 4.0
QUARTERS = 16
EARNINGS_CYCLE = 63  # sessions between reports

_NY = ZoneInfo("America/New_York")
_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_FUNDAMENTAL_KEYS = (
    "revenue",
    "eps_diluted",
    "gross_margin",
    "operating_margin",
    "fcf",
    "net_debt",
    "shares",
)

_Kind = Literal["trend", "range", "reverse", "mixed", "etf"]


@dataclass(frozen=True)
class _Profile:
    symbol: str
    name: str
    type: Literal["stock", "etf"]
    kind: _Kind
    base: float
    sigma: float  # daily volatility of log price
    mu: float  # daily log drift for trend, reverse (magnitude), etf
    volume: float  # baseline daily shares
    leader: str | None = None  # shares regimes and a fraction of shocks with this symbol
    rho: float = 0.0
    split_index: int | None = None  # session index from the oldest bar
    earnings_offset: int | None = None  # sessions after the end date of the next report


_PROFILES: tuple[_Profile, ...] = (
    _Profile("FXA", "Fixture Trend Corp", "stock", "trend", 40.0, 0.008, 0.0018, 2.0e6),
    _Profile("FXB", "Fixture Range Inc", "stock", "range", 80.0, 0.012, 0.0, 1.5e6),
    _Profile("FXC", "Fixture Reversal Co", "stock", "reverse", 60.0, 0.010, 0.0016, 1.8e6),
    _Profile("FXD", "Fixture Decline Ltd", "stock", "trend", 120.0, 0.010, -0.0012, 1.2e6),
    _Profile(
        "FXE", "Fixture Split Corp", "stock", "mixed", 55.0, 0.012, 0.0, 2.5e6, split_index=400
    ),
    _Profile("FXF", "Fixture Leader Inc", "stock", "mixed", 95.0, 0.013, 0.0, 3.0e6),
    _Profile("FXG", "Fixture Follower Inc", "stock", "mixed", 70.0, 0.014, 0.0, 2.2e6, "FXF", 0.9),
    _Profile(
        "FXH", "Fixture Event Co", "stock", "mixed", 150.0, 0.011, 0.0, 1.1e6, earnings_offset=3
    ),
    _Profile("FXI", "Fixture Momentum Co", "stock", "mixed", 30.0, 0.016, 0.0, 4.0e6),
    _Profile("FXJ", "Fixture Value Co", "stock", "mixed", 210.0, 0.009, 0.0, 0.9e6),
    _Profile("FXK", "Fixture Broad ETF", "etf", "mixed", 100.0, 0.006, 0.0, 8.0e6),
    _Profile("FXL", "Fixture Sector ETF", "etf", "mixed", 50.0, 0.008, 0.0, 6.0e6),
    _Profile("SPY", "Fixture S&P 500 Stand-in", "etf", "etf", 450.0, 0.007, 0.0004, 3.0e7),
    _Profile(
        "QQQ", "Fixture Nasdaq 100 Stand-in", "etf", "etf", 380.0, 0.009, 0.0006, 2.0e7, "SPY", 0.85
    ),
)
_BY_SYMBOL = {p.symbol: p for p in _PROFILES}

_MIXED_REGIMES = ((0.0012, 0.0), (-0.0012, 0.0), (0.0, 0.04))  # (daily drift, reversion speed)
_RANGE_KAPPA = 0.03


def _permissive_profile(symbol: str) -> _Profile:
    h = int.from_bytes(sha256(symbol.encode()).digest()[:8], "big")
    return _Profile(
        symbol,
        f"Fixture {symbol}",
        "stock",
        "mixed",
        20.0 + h % 280,
        0.009 + ((h >> 8) % 8) * 0.001,
        0.0,
        1.0e6 + ((h >> 16) % 40) * 1.0e5,
    )


def _regimes(seed: int, regime_key: str, prof: _Profile) -> list[tuple[float, float]]:
    """(daily drift, reversion speed) for each session index counted from the oldest."""
    n = DAILY_SESSIONS
    if prof.kind == "trend":
        return [(prof.mu, 0.0)] * n
    if prof.kind == "etf":
        return [(prof.mu, 0.0)] * n
    if prof.kind == "range":
        return [(0.0, _RANGE_KAPPA)] * n
    if prof.kind == "reverse":
        half = n // 2
        return [(prof.mu, 0.0)] * half + [(-prof.mu, 0.0)] * (n - half)
    rng = Random(f"{seed}:{regime_key}:regimes")
    out: list[tuple[float, float]] = []
    while len(out) < n:
        regime = rng.choice(_MIXED_REGIMES)
        out.extend([regime] * rng.randint(40, 120))
    return out[:n]


@dataclass(frozen=True)
class _Series:
    daily: tuple[Bar, ...]
    daily_dates: tuple[date, ...]
    intraday: tuple[Bar, ...]
    intraday_dates: tuple[date, ...]  # session date of each intraday bar


def _daily_ts(day: date) -> datetime:
    return datetime.combine(day, time(0), tzinfo=_NY)


def _quarter_end_on_or_before(day: date) -> date:
    for month, dom in ((12, 31), (9, 30), (6, 30), (3, 31)):
        candidate = date(day.year, month, dom)
        if candidate <= day:
            return candidate
    return date(day.year - 1, 12, 31)


def _normals(seed: int, symbol: str, k: int, count: int) -> list[float]:
    rng = Random(f"{seed}:{symbol}:{k}:z")
    return [rng.gauss(0.0, 1.0) for _ in range(count)]


class FixtureUniverse:
    """The synthetic dataset: calendar, per-symbol series, and fundamentals schedules."""

    def __init__(self, seed: int, end_date: date, *, permissive: bool = False) -> None:
        self.seed = seed
        self.end_date = end_date
        self.permissive = permissive
        window = sessions_between(end_date - timedelta(days=1300), end_date + timedelta(days=130))
        pos = bisect_right(window, end_date) - 1
        if pos + 1 < DAILY_SESSIONS or window[pos] != end_date:
            msg = f"SUPERTRENDS_FIXTURE_END_DATE {end_date} is not an XNYS session with 3 years"
            raise ValueError(msg)
        self.sessions: list[date] = window[pos + 1 - DAILY_SESSIONS : pos + 1]
        self.future_sessions: list[date] = window[pos + 1 :]
        self._series: dict[str, _Series] = {}

    @staticmethod
    def symbols() -> list[str]:
        """The fixed universe, in order."""
        return [p.symbol for p in _PROFILES]

    def profile(self, symbol: str) -> _Profile | None:
        """Profile of a universe symbol, a hashed profile when permissive, else None."""
        known = _BY_SYMBOL.get(symbol)
        if known is not None:
            return known
        if self.permissive and _SYMBOL_RE.match(symbol):
            return _permissive_profile(symbol)
        return None

    def series(self, symbol: str) -> _Series | None:
        """Generated bars for a symbol (cached), or None for an unknown symbol."""
        cached = self._series.get(symbol)
        if cached is not None:
            return cached
        prof = self.profile(symbol)
        if prof is None:
            return None
        built = self._build(prof)
        self._series[symbol] = built
        return built

    def split_date(self, symbol: str) -> date | None:
        """Ex-date of the symbol's split, if it has one."""
        prof = self.profile(symbol)
        if prof is None or prof.split_index is None:
            return None
        return self.sessions[prof.split_index]

    def _build(self, prof: _Profile) -> _Series:  # noqa: PLR0915
        seed, n_total = self.seed, DAILY_SESSIONS
        regimes = _regimes(seed, prof.leader or prof.symbol, prof)
        logp = log(prof.base)
        price = round(prof.base, 4)
        anchor = logp
        last_regime: tuple[float, float] | None = None
        daily: list[Bar] = []
        intraday: list[Bar] = []
        intraday_dates: list[date] = []
        sqrt_full = sqrt(FULL_DAY_BARS)

        for i, day in enumerate(self.sessions):
            k = n_total - 1 - i
            mu, kappa = regimes[i]
            if last_regime is not None and (mu, kappa) != last_regime:
                anchor = logp
            last_regime = (mu, kappa)
            rng = Random(f"{seed}:{prof.symbol}:{k}")
            gap_z, big = rng.gauss(0.0, 1.0), rng.random()
            gap = prof.sigma * 0.5 * gap_z
            if big < 0.03:
                gap = copysign(rng.uniform(0.03, 0.06), gap_z)
            open_ = round(price * exp(gap), 4)
            drift = mu + kappa * (anchor - log(open_))
            is_intraday = k < INTRADAY_SESSIONS
            count = FULL_DAY_BARS if is_intraday else 1
            zs = _normals(seed, prof.symbol, k, count)
            if prof.leader is not None:
                lead = _normals(seed, prof.leader, k, count)
                own = sqrt(1.0 - prof.rho**2)
                zs = [prof.rho * a + own * b for a, b in zip(lead, zs, strict=True)]
            vol_noise = rng.gauss(0.0, 1.0)

            if is_intraday:
                opened, closed = session_bounds(day)
                n_bars = int((closed - opened).total_seconds() // 300)
                step_sigma = prof.sigma / sqrt_full
                step_drift = drift / FULL_DAY_BARS
                rows: list[tuple[datetime, float, float, float, float]] = []
                p = open_
                for j in range(n_bars):
                    c = round(p * exp(step_drift + step_sigma * zs[j]), 4)
                    h = round(max(p, c) * exp(step_sigma * 0.6 * rng.random()), 4)
                    lo = round(min(p, c) * exp(-step_sigma * 0.6 * rng.random()), 4)
                    rows.append((opened + timedelta(minutes=5 * j), p, h, lo, c))
                    p = c
                close = p
                day_ret = abs(log(close / open_))
                total = self._day_volume(prof, day, vol_noise, day_ret, n_bars / FULL_DAY_BARS)
                weights = [0.6 + 2.4 * (2.0 * (j + 0.5) / n_bars - 1.0) ** 2 for j in range(n_bars)]
                scale = total / sum(weights)
                vols = [int(w * scale) for w in weights]
                for (ts, o, h, lo, c), v in zip(rows, vols, strict=True):
                    intraday.append(Bar(prof.symbol, ts, o, h, lo, c, v))
                    intraday_dates.append(day)
                day_bar = Bar(
                    prof.symbol,
                    _daily_ts(day),
                    open_,
                    max(r[2] for r in rows),
                    min(r[3] for r in rows),
                    close,
                    sum(vols),
                )
            else:
                close = round(open_ * exp(drift + prof.sigma * zs[0]), 4)
                high = round(max(open_, close) * exp(prof.sigma * 0.6 * rng.random()), 4)
                low = round(min(open_, close) * exp(-prof.sigma * 0.6 * rng.random()), 4)
                day_ret = abs(log(close / open_))
                vol = self._day_volume(prof, day, vol_noise, day_ret, 1.0)
                day_bar = Bar(prof.symbol, _daily_ts(day), open_, high, low, close, int(vol))
            daily.append(day_bar)
            price = close
            logp = log(close)

        return _Series(
            tuple(daily),
            tuple(b.ts.date() for b in daily),
            tuple(intraday),
            tuple(intraday_dates),
        )

    @staticmethod
    def _day_volume(prof: _Profile, day: date, noise: float, day_ret: float, frac: float) -> float:
        """Volume pattern: log-normal noise, weekday effect, surge on large moves."""
        weekday = {0: 0.95, 4: 0.9}.get(day.weekday(), 1.05)
        surge = 1.0 + 1.5 * max(0.0, day_ret / prof.sigma - 1.2)
        return prof.volume * exp(0.25 * noise) * weekday * surge * frac

    # --- fundamentals schedule ---

    def quarter_ends(self) -> list[date]:
        """Last QUARTERS fiscal quarter ends whose financials are known by the end date."""
        out: list[date] = []
        cursor = self.end_date - timedelta(days=30)
        while len(out) < QUARTERS:
            q_end = _quarter_end_on_or_before(cursor)
            out.append(q_end)
            cursor = q_end - timedelta(days=1)
        return out[::-1]

    def earnings_sessions(self, symbol: str) -> list[date]:
        """Earnings dates: every 63 sessions, next one a stable few sessions after the end."""
        prof = self.profile(symbol)
        if prof is None or prof.type == "etf":
            return []
        offset = prof.earnings_offset
        if offset is None:
            offset = 4 + int.from_bytes(sha256(f"{self.seed}:{symbol}".encode()).digest()[:2]) % 56
        everything = self.sessions + self.future_sessions
        end_pos = len(self.sessions) - 1
        out: list[date] = []
        idx = end_pos + offset
        while idx >= 0:
            if idx < len(everything):
                out.append(everything[idx])
            idx -= EARNINGS_CYCLE
        return sorted(out)


class FixtureProvider:
    """MarketDataProvider over the synthetic universe."""

    name = "fixture"
    capabilities = ProviderCapabilities(
        intraday=True, trades=False, adjusted=True, grouped_daily=True, reference=True
    )

    def __init__(self, universe: FixtureUniverse) -> None:
        self.universe = universe
        self.calls: deque[tuple[str, str]] = deque(maxlen=10_000)

    @classmethod
    def from_settings(cls, settings: Settings) -> "FixtureProvider":
        """Build from SUPERTRENDS_FIXTURE_* settings (shares the cached dataset)."""
        return cls(_universe_from_settings(settings))

    def _bars(self, symbol: str, *, daily: bool, start: date, end: date) -> list[Bar]:
        series = self.universe.series(symbol)
        if series is None:
            return []
        bars, dates = (
            (series.daily, series.daily_dates)
            if daily
            else (series.intraday, series.intraday_dates)
        )
        return list(bars[bisect_left(dates, start) : bisect_right(dates, end)])

    def daily_bars(self, symbol: str, start: date, end: date) -> Sequence[Bar]:
        self.calls.append(("daily_bars", symbol))
        return self._bars(symbol, daily=True, start=start, end=end)

    def grouped_daily(self, session: date) -> Sequence[Bar]:
        self.calls.append(("grouped_daily", ""))
        out: list[Bar] = []
        for symbol in self.universe.symbols():
            out.extend(self._bars(symbol, daily=True, start=session, end=session))
        return out

    def intraday_bars(
        self, symbol: str, start: date, end: date, minutes: Literal[5] = 5
    ) -> Sequence[Bar]:
        self.calls.append(("intraday_bars", symbol))
        return self._bars(symbol, daily=False, start=start, end=end)

    def corporate_actions(self, symbol: str, start: date, end: date) -> Sequence[CorporateAction]:
        self.calls.append(("corporate_actions", symbol))
        ex = self.universe.split_date(symbol)
        if ex is None or not start <= ex <= end:
            return []
        return [CorporateAction(symbol, ex, "split", SPLIT_RATIO, None)]

    def resolve_symbol(self, symbol: str) -> SymbolInfo | None:
        self.calls.append(("resolve_symbol", symbol))
        prof = self.universe.profile(symbol)
        if prof is None:
            return None
        return SymbolInfo(prof.symbol, prof.name, prof.type, True)

    def trades(self, symbol: str, session: date) -> Sequence[object]:
        msg = "the fixture provider has no tick trades"
        raise CapabilityNotSupported(msg)

    def status(self) -> ProviderStatus:
        return ProviderStatus(self.name, "ok", None)


class FixtureFundamentals:
    """FundamentalsProvider over the synthetic universe (ETFs have no financials)."""

    name = "fixture"
    supports_forward_estimates = False

    def __init__(self, universe: FixtureUniverse) -> None:
        self.universe = universe

    @classmethod
    def from_settings(cls, settings: Settings) -> "FixtureFundamentals":
        """Build from SUPERTRENDS_FIXTURE_* settings (shares the cached dataset)."""
        return cls(_universe_from_settings(settings))

    def quarterly_financials(self, symbol: str, since: date) -> Sequence[QuarterlyFinancials]:
        prof = self.universe.profile(symbol)
        if prof is None or prof.type == "etf":
            return []
        rng = Random(f"{self.universe.seed}:{symbol}:fin")
        revenue = prof.volume * prof.base * (0.5 + rng.random())
        growth = 0.01 + 0.03 * rng.random()
        shares = prof.volume * (20.0 + 10.0 * rng.random())
        gross = 0.35 + 0.3 * rng.random()
        oper = gross * (0.3 + 0.3 * rng.random())
        rows: list[QuarterlyFinancials] = []
        for q_end in self.universe.quarter_ends():
            revenue *= 1.0 + growth + 0.02 * rng.gauss(0.0, 1.0)
            gross = min(0.9, max(0.05, gross + 0.005 * rng.gauss(0.0, 1.0)))
            oper = min(gross, max(-0.1, oper + 0.005 * rng.gauss(0.0, 1.0)))
            shares *= 1.0 + 0.002 * rng.gauss(0.0, 1.0)
            net_income = revenue * oper * 0.8
            metrics: dict[str, float | None] = {
                "revenue": float(round(revenue, 2)),
                "eps_diluted": float(round(net_income / shares, 4)),
                "gross_margin": float(round(gross, 4)),
                "operating_margin": float(round(oper, 4)),
                "fcf": float(round(net_income * (0.8 + 0.4 * rng.random()), 2)),
                "net_debt": float(round(revenue * (rng.random() - 0.3), 2)),
                "shares": float(round(shares, 0)),
            }
            if q_end >= since:
                known = datetime.combine(q_end + timedelta(days=30), time(13, 0), tzinfo=UTC)
                rows.append(QuarterlyFinancials(symbol, q_end, known, metrics))
        return rows

    def forward_estimates(self, symbol: str) -> Sequence[ForwardEstimate]:
        return []

    def earnings_dates(self, symbol: str, start: date, end: date) -> Sequence[EarningsDate]:
        last_known = self.universe.end_date + timedelta(days=30)
        return [
            EarningsDate(symbol, d, confirmed=d <= last_known)
            for d in self.universe.earnings_sessions(symbol)
            if start <= d <= end
        ]

    def status(self) -> ProviderStatus:
        return ProviderStatus(self.name, "ok", None)


@lru_cache(maxsize=4)
def _cached_universe(seed: int, end_date: date, permissive: bool) -> FixtureUniverse:
    return FixtureUniverse(seed, end_date, permissive=permissive)


def _universe_from_settings(settings: Settings) -> FixtureUniverse:
    end = (
        date.fromisoformat(settings.fixture_end_date)
        if settings.fixture_end_date
        else last_completed_session()
    )
    return _cached_universe(settings.fixture_seed, end, settings.fixture_permissive)
