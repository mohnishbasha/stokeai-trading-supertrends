# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Estimated buy and sell volume flow (owned by S2-T07; BUILD_PROMPT Factor 10).

Per bar: `buy = volume * (close - low) / (high - low)` when `high > low`, else all volume is buy
when `close >= prev_close` and all sell otherwise; `sell = volume - buy`. Per session:
`delta = sum(buy) - sum(sell)` and `delta_pct = delta / sum(volume)` (NaN for a zero-volume
session). `delta_pct_10` is the mean of the finite `delta_pct` values over the last 10 sessions.

Clock-free contract: the indicator never converts time zones. The caller passes 5-minute bar
start times as session-local (America/New_York) wall-clock `datetime64` values and the session
dates as `datetime64[D]`. Only bars starting in [09:30, 16:00) count (regular session).

Previous close for the zero-range rule: the close of the previous regular-session bar in the
input (the prior session's last bar for a session's first bar); the very first bar has no
previous close and is treated as `close >= prev_close` (all buy). The daily path uses the prior
daily close and the same first-bar rule (PRD A-07, A-23).

Quality, in order: `trades` (a plug-in classifier with at least `min_intraday_sessions` of the
last `window` sessions), `intraday` (5-minute bars on at least that many), else
`daily_estimate` (same formula on daily bars, flagged by `daily_fallback`). The 0.6 weight
multiplier for `daily_estimate` belongs to scoring.
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "FlowQuality",
    "FlowResult",
    "TradesClassifier",
    "estimate_order_flow",
    "split_volume",
]

FloatArray = NDArray[np.float64]

SESSION_OPEN_MIN = 9 * 60 + 30
SESSION_CLOSE_MIN = 16 * 60


class FlowQuality(StrEnum):
    """Data quality of the order flow estimate."""

    INTRADAY = "intraday"
    DAILY_ESTIMATE = "daily_estimate"
    TRADES = "trades"


class TradesClassifier(Protocol):
    """Plug-in for tick-rule classification of trade prints (not implemented in v1)."""

    def delta_pct(self, sessions: NDArray[np.datetime64]) -> FloatArray:
        """Per-session delta percent for the given session dates; NaN where unavailable."""
        ...


@dataclass(frozen=True)
class FlowResult:
    """Order flow per daily session plus the 10-session summary."""

    sessions: NDArray[np.datetime64]
    buy: FloatArray
    sell: FloatArray
    delta: FloatArray
    delta_pct: FloatArray
    delta_pct_10: float
    quality: FlowQuality
    daily_fallback: bool
    intraday_sessions: int


def split_volume(
    high: FloatArray, low: FloatArray, close: FloatArray, volume: FloatArray, prev_close: FloatArray
) -> tuple[FloatArray, FloatArray]:
    """Split each bar's volume into estimated (buy, sell); `buy + sell == volume`.

    Inputs are equal-length arrays; `prev_close` is only used on zero-range bars. No warm-up.
    """
    _check_lengths(high, low, close, volume, prev_close)
    rng = high - low
    with np.errstate(divide="ignore", invalid="ignore"):
        ranged = volume * np.clip((close - low) / rng, 0.0, 1.0)
    buy = np.where(rng > 0.0, ranged, np.where(close >= prev_close, volume, 0.0))
    return buy, volume - buy


def estimate_order_flow(  # noqa: PLR0913, PLR0917
    sessions: NDArray[np.datetime64],
    d_high: FloatArray,
    d_low: FloatArray,
    d_close: FloatArray,
    d_volume: FloatArray,
    bar_start: NDArray[np.datetime64] | None = None,
    high: FloatArray | None = None,
    low: FloatArray | None = None,
    close: FloatArray | None = None,
    volume: FloatArray | None = None,
    trades: TradesClassifier | None = None,
    window: int = 10,
    min_intraday_sessions: int = 8,
) -> FlowResult:
    """Estimate order flow per daily session and the mean delta percent over the last `window`.

    `sessions` (datetime64[D], ascending) and the `d_*` daily arrays define the output grid. The
    intraday arguments (`bar_start` and OHLCV of 5-minute bars) are all given or all omitted.
    Per-session output arrays are NaN for sessions without data on the chosen path. Warm-up: on
    the daily path `delta_pct_10` is NaN with fewer than `window` sessions.
    """
    _check_lengths(sessions, d_high, d_low, d_close, d_volume)
    intraday_args = (bar_start, high, low, close, volume)
    given = [a is not None and len(a) > 0 for a in intraday_args]
    if any(a is not None for a in intraday_args) and not all(a is not None for a in intraday_args):
        msg = "bar_start, high, low, close and volume must be given together"
        raise ValueError(msg)
    nan = np.full(len(sessions), np.nan)
    tail = slice(max(len(sessions) - window, 0), None)

    if trades is not None:
        pct_t = np.asarray(trades.delta_pct(sessions), dtype=np.float64)
        if int(np.isfinite(pct_t[tail]).sum()) >= min_intraday_sessions:
            return FlowResult(
                sessions, nan, nan, nan, pct_t, _mean(pct_t[tail]), FlowQuality.TRADES, False, 0
            )

    n_intraday = 0
    if any(given):
        assert bar_start is not None  # noqa: S101 - narrowing for mypy
        assert high is not None  # noqa: S101
        assert low is not None  # noqa: S101
        assert close is not None  # noqa: S101
        assert volume is not None  # noqa: S101
        buy, sell, counts = _intraday_sessions(sessions, bar_start, high, low, close, volume)
        n_intraday = int((counts[tail] > 0).sum())
        if n_intraday >= min_intraday_sessions:
            buy[counts == 0] = np.nan
            sell[counts == 0] = np.nan
            delta, pct = _delta(buy, sell)
            return FlowResult(
                sessions,
                buy,
                sell,
                delta,
                pct,
                _mean(pct[tail]),
                FlowQuality.INTRADAY,
                False,
                n_intraday,
            )

    prev = np.concatenate([d_close[:1], d_close[:-1]])
    buy, sell = split_volume(d_high, d_low, d_close, d_volume, prev)
    delta, pct = _delta(buy, sell)
    mean = _mean(pct[tail]) if len(sessions) >= window else math.nan
    return FlowResult(
        sessions, buy, sell, delta, pct, mean, FlowQuality.DAILY_ESTIMATE, True, n_intraday
    )


def _check_lengths(*arrays: NDArray[np.generic]) -> None:
    if len({len(a) for a in arrays}) > 1:
        msg = "input arrays must have the same length"
        raise ValueError(msg)


def _mean(x: FloatArray) -> float:
    finite = x[np.isfinite(x)]
    return float(finite.mean()) if len(finite) else math.nan


def _delta(buy: FloatArray, sell: FloatArray) -> tuple[FloatArray, FloatArray]:
    delta = buy - sell
    total = buy + sell
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = np.where(total > 0.0, delta / total, np.nan)
    return delta, pct


def _intraday_sessions(  # noqa: PLR0913, PLR0917
    sessions: NDArray[np.datetime64],
    bar_start: NDArray[np.datetime64],
    high: FloatArray,
    low: FloatArray,
    close: FloatArray,
    volume: FloatArray,
) -> tuple[FloatArray, FloatArray, NDArray[np.int64]]:
    """Per-session buy and sell sums and regular-session bar counts."""
    _check_lengths(bar_start, high, low, close, volume)
    if len(bar_start) > 1 and bool(
        (np.diff(bar_start.astype("datetime64[m]")) <= np.timedelta64(0, "m")).any()
    ):
        msg = "bar_start must be sorted ascending without duplicates"
        raise ValueError(msg)
    minutes = bar_start.astype("datetime64[m]")
    day = minutes.astype("datetime64[D]")
    minute_of_day = (minutes - day.astype("datetime64[m]")).astype(np.int64)
    regular = (minute_of_day >= SESSION_OPEN_MIN) & (minute_of_day < SESSION_CLOSE_MIN)
    h, lo, c, v, day = high[regular], low[regular], close[regular], volume[regular], day[regular]
    prev = np.concatenate([c[:1], c[:-1]])
    buy_bar, sell_bar = split_volume(h, lo, c, v, prev)
    n = len(sessions)
    idx = np.minimum(np.searchsorted(sessions, day), max(n - 1, 0))
    valid = (sessions[idx] == day) if n else np.zeros(len(day), dtype=bool)
    idx = idx[valid]
    buy = np.bincount(idx, weights=buy_bar[valid], minlength=n)
    sell = np.bincount(idx, weights=sell_bar[valid], minlength=n)
    counts = np.bincount(idx, minlength=n).astype(np.int64)
    return buy, sell, counts
