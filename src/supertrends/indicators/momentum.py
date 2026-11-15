# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Momentum indicators: MACD and related oscillators (owned by S2-T03; Factor 3).

Spec: BUILD_PROMPT Factor 3 (MACD 12, 26, 9 on daily closes; weekly MACD as evidence) and
ADR-033 (weekly resample). Pure functions; the value at t uses only bars <= t.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from supertrends.indicators.primitives import ema, resample_weekly
from supertrends.indicators.trend import Cross, last_cross

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

__all__ = ["Macd", "hist_run", "macd", "macd_signal_cross", "macd_weekly"]


@dataclass(frozen=True)
class Macd:
    """MACD line, signal line, and histogram."""

    line: FloatArray
    signal: FloatArray
    hist: FloatArray


def _check_periods(fast: int, slow: int, signal: int) -> None:
    for name, v in (("fast", fast), ("slow", slow), ("signal", signal)):
        if v < 1:
            msg = f"window {name} must be >= 1, got {v}"
            raise ValueError(msg)
    if fast >= slow:
        msg = f"fast ({fast}) must be smaller than slow ({slow})"
        raise ValueError(msg)


def macd(close: FloatArray, fast: int = 12, slow: int = 26, signal: int = 9) -> Macd:
    """MACD: `line = EMA(fast) - EMA(slow)`, `signal = EMA(line, signal)`, `hist = line - signal`.

    Each EMA is seeded with the SMA of its first n defined values (primitives.ema). Warm-up: line
    is NaN before index slow-1; signal and hist before slow+signal-2 (33 for 12/26/9). Lag: that of
    the slow EMA plus the signal EMA.
    """
    _check_periods(fast, slow, signal)
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return Macd(line, sig, line - sig)


def _asof_ema(done: FloatArray, series: FloatArray, week: int, x: float, n: int) -> float:
    """EMA at weekly bar `week` if that bar's input were `x`, given the EMA of completed weeks.

    `done` is the EMA of the completed weeks 0..week-1 and `series` the input they were computed
    from. Mirrors the primitives seeding: SMA of the first n defined values, then recursion.
    """
    if week >= 1 and not np.isnan(done[week - 1]):
        return float(done[week - 1] + 2.0 / (n + 1) * (x - done[week - 1]))
    if np.isnan(x):
        return float("nan")
    defined = np.flatnonzero(~np.isnan(series[:week]))
    first = int(defined[0]) if len(defined) else week
    if week != first + n - 1:
        return float("nan")
    return float((series[first:week].sum() + x) / n)


def macd_weekly(
    dates: NDArray[np.datetime64],
    close: FloatArray,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Macd:
    """Weekly MACD mapped onto the daily index without look-ahead.

    Daily closes are resampled to ISO-week bars (`resample_weekly`, ADR-033). The value on day t is
    the MACD of the weekly series made of all completed weeks before t's week plus t's own
    in-progress week, whose close is the close of day t (the weekly bar as known on day t). It is
    computed incrementally from the EMA state of completed weeks, so cost is O(n) and no value
    depends on any bar after t. On the last session of a week it equals the finished weekly bar's
    MACD. Warm-up: NaN until enough weeks exist (line: slow weeks; signal: slow+signal-1 weeks,
    counting the in-progress week).
    """
    _check_periods(fast, slow, signal)
    size = len(close)
    line = np.full(size, np.nan, dtype=np.float64)
    sig = line.copy()
    if size == 0:
        return Macd(line, sig, line.copy())
    # Only the weekly close and the daily-to-week mapping are used; other fields are dummies.
    weekly = resample_weekly(dates, close, close, close, close, close)
    wclose = weekly.close
    done_fast, done_slow = ema(wclose, fast), ema(wclose, slow)
    done_line = done_fast - done_slow
    done_sig = ema(done_line, signal)
    for t, w in enumerate(weekly.week_index.tolist()):
        x = float(close[t])
        ln = _asof_ema(done_fast, wclose, w, x, fast) - _asof_ema(done_slow, wclose, w, x, slow)
        line[t] = ln
        sig[t] = _asof_ema(done_sig, done_line, w, ln, signal)
    return Macd(line, sig, line - sig)


def macd_signal_cross(line: FloatArray, signal: FloatArray, lookback: int = 3) -> Cross | None:
    """Most recent line-vs-signal cross within the last `lookback` bars (default 3), with its bar.

    Bullish (+1): `line[t-1] <= signal[t-1]` and `line[t] > signal[t]`; bearish (-1) mirrors it
    (see `trend.cross_events` for equality and NaN handling). Returns None when there is none.
    """
    return last_cross(line, signal, lookback)


def hist_run(hist: FloatArray, bars: int = 3) -> IntArray:
    """Histogram run flag at every bar: +1 rising, -1 falling, 0 otherwise.

    +1 at t when the histogram rose on each of the last `bars` bars (default 3), i.e.
    `hist[t-k] > hist[t-k-1]` for k = 0..bars-1 (so bars+1 defined values; equality breaks the
    run). -1 mirrors it. NaN anywhere in the window gives 0. Warm-up: 0 for the first `bars` bars.
    """
    if bars < 1:
        msg = f"bars must be >= 1, got {bars}"
        raise ValueError(msg)
    out = np.zeros(len(hist), dtype=np.int64)
    if len(hist) <= bars:
        return out
    with np.errstate(invalid="ignore"):
        diff = np.diff(hist)  # diff[i] is the change into bar i+1
        rising = np.r_[0, np.cumsum(diff > 0)]
        falling = np.r_[0, np.cumsum(diff < 0)]
    idx = np.arange(bars, len(hist))  # the window of `bars` diffs ending at bar t
    all_up = rising[idx] - rising[idx - bars] == bars
    all_down = falling[idx] - falling[idx - bars] == bars
    out[bars:] = np.where(all_up, 1, np.where(all_down, -1, 0))
    return out
