# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Trend indicators: SMA stack, slope, crosses, ADX (owned by S2-T03; Factors 2 and 3).

Spec: BUILD_PROMPT Signal Engine Specification, Factor 2 (trend: SMA 20/50/200, slope, golden and
death cross) and the regime ADX(14). All functions are pure and O(n), and never read a bar after
t when producing the value at t.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from supertrends.indicators.primitives import rma, sma, true_range

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

__all__ = [
    "Adx",
    "Cross",
    "SmaStack",
    "adx",
    "cross_events",
    "last_cross",
    "sma_slope",
    "sma_stack",
]


@dataclass(frozen=True)
class SmaStack:
    """Three simple moving averages."""

    sma20: FloatArray
    sma50: FloatArray
    sma200: FloatArray


@dataclass(frozen=True)
class Cross:
    """A cross event: `index` is the bar where it happened, `direction` +1 golden, -1 death."""

    index: int
    direction: int


@dataclass(frozen=True)
class Adx:
    """ADX with directional indicators."""

    adx: FloatArray
    plus_di: FloatArray
    minus_di: FloatArray


def _check(n: int, name: str) -> None:
    if n < 1:
        msg = f"{name} must be >= 1, got {n}"
        raise ValueError(msg)


def sma_stack(close: FloatArray, short: int = 20, mid: int = 50, long: int = 200) -> SmaStack:
    """SMA of `close` over `short`, `mid`, and `long` bars (defaults 20, 50, 200).

    Warm-up: NaN for the first window-1 bars of each average. Lag: (window-1)/2 bars.
    """
    return SmaStack(sma(close, short), sma(close, mid), sma(close, long))


def sma_slope(values: FloatArray, bars: int = 5) -> FloatArray:
    """Slope over `bars` bars, defined exactly as `values[t] - values[t - bars]`.

    It is a plain difference (not per bar, not normalized); Factor 2 uses only its sign (positive
    rising, negative falling, zero flat). Warm-up: NaN for the first `bars` bars and wherever
    either operand is NaN. Lag: inherits the SMA lag.
    """
    _check(bars, "bars")
    out = np.full(len(values), np.nan, dtype=np.float64)
    if len(values) > bars:
        out[bars:] = values[bars:] - values[:-bars]
    return out


def cross_events(a: FloatArray, b: FloatArray) -> IntArray:
    """Cross of `a` against `b` at every bar: +1 golden, -1 death, 0 none.

    A golden cross at t means `a[t-1] <= b[t-1]` and `a[t] > b[t]`; a death cross means
    `a[t-1] >= b[t-1]` and `a[t] < b[t]`. Equality on the prior bar therefore counts as "not
    yet above" (or "not yet below"), so a touch followed by a break fires once, at the break bar.
    Bars where either input is NaN, on t or t-1, are never crosses. Uses only bars <= t.
    """
    if len(a) != len(b):
        msg = "input arrays must have the same length"
        raise ValueError(msg)
    out = np.zeros(len(a), dtype=np.int64)
    if len(a) < 2:
        return out
    prev_a, prev_b, cur_a, cur_b = a[:-1], b[:-1], a[1:], b[1:]
    with np.errstate(invalid="ignore"):  # NaN comparisons are False, which is what we want
        out[1:][(prev_a <= prev_b) & (cur_a > cur_b)] = 1
        out[1:][(prev_a >= prev_b) & (cur_a < cur_b)] = -1
    return out


def last_cross(a: FloatArray, b: FloatArray, lookback: int) -> Cross | None:
    """Most recent cross of `a` vs `b` whose bar is among the last `lookback` bars.

    The window is bars `n - lookback .. n - 1` (the last bar counts as one of the lookback
    bars). Returns the cross bar index and direction, or None.
    """
    _check(lookback, "lookback")
    events = cross_events(a, b)
    start = max(0, len(events) - lookback)
    hits = np.flatnonzero(events[start:])
    if len(hits) == 0:
        return None
    idx = start + int(hits[-1])
    return Cross(idx, int(events[idx]))


def _ratio(num: FloatArray, den: FloatArray) -> FloatArray:
    """100 * num / den, 0 where den is 0, NaN where den is NaN."""
    positive = den > 0
    out = np.where(positive, 100.0 * num / np.where(positive, den, 1.0), 0.0)
    return np.where(np.isnan(den), np.nan, out)


def adx(high: FloatArray, low: FloatArray, close: FloatArray, n: int = 14) -> Adx:
    """ADX with +DI and -DI, Wilder formulation (ARCHITECTURE ADR-054).

    For t >= 1: `up = high[t] - high[t-1]`, `down = low[t-1] - low[t]`;
    `+DM = up if up > down and up > 0 else 0`, `-DM = down if down > up and down > 0 else 0`;
    TR is the true range. TR, +DM, -DM are smoothed with the Wilder RMA over bars 1..n (seeded
    with their mean, which is the classic sum form scaled by 1/n, so the ratios are identical).
    `+DI = 100 * RMA(+DM) / RMA(TR)`, `-DI` likewise, `DX = 100 * |+DI - -DI| / (+DI + -DI)`,
    `ADX = RMA(DX, n)`. A zero denominator gives 0 (flat series: DI = DX = ADX = 0).

    Warm-up: DI is NaN before index n, ADX before index 2n-1. Lag: Wilder smoothing, roughly n.
    """
    _check(n, "window n")
    if not len(high) == len(low) == len(close):
        msg = "input arrays must have the same length"
        raise ValueError(msg)
    size = len(close)
    plus_di = np.full(size, np.nan, dtype=np.float64)
    minus_di, dx = plus_di.copy(), plus_di.copy()
    if size <= n:
        return Adx(plus_di.copy(), plus_di, minus_di)
    up = high[1:] - high[:-1]
    down = low[:-1] - low[1:]
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    smooth_tr = rma(true_range(high, low, close)[1:], n)
    pdi = _ratio(rma(plus_dm, n), smooth_tr)
    mdi = _ratio(rma(minus_dm, n), smooth_tr)
    plus_di[1:], minus_di[1:] = pdi, mdi
    total = pdi + mdi
    dx[1:] = _ratio(np.abs(pdi - mdi), total)
    return Adx(rma(dx, n), plus_di, minus_di)
