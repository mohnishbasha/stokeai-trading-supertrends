# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Indicator primitives (Signal Engine Specification, Conventions; ADR-033; ADR-053).

Every function is pure. Inputs are 1-D float64 numpy arrays; outputs are float64 arrays of the
same length with NaN during warm-up, or frozen dataclass records. The value at bar t uses only
bars at or before t. Pivots and ZigZag swings confirm late and report the bar at which they
became known.

NaN policy: moving averages and windowed statistics (`sma`, `stdev`, `percentile_rank`,
`linreg_slope`) are NaN wherever the window holds a NaN. `ema` and `rma` skip leading NaN
(the seed uses the first n non-NaN values) and are NaN from the first NaN that follows the
seed onward. A window larger than the input yields all NaN. Bars with NaN prices never form a
pivot.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
DateArray = NDArray[np.datetime64]
IntArray = NDArray[np.int64]

__all__ = [
    "Pivot",
    "Swing",
    "WeeklyBars",
    "ZigZag",
    "atr",
    "ema",
    "linreg_slope",
    "obv",
    "percentile_rank",
    "pivot_confirmation_bar",
    "pivot_masks",
    "pivots",
    "resample_weekly",
    "rma",
    "rsi",
    "sma",
    "stdev",
    "true_range",
    "zigzag",
    "zigzag_threshold",
]


@dataclass(frozen=True)
class Pivot:
    """A confirmed pivot high or low.

    `index` is the bar of the extreme; `confirmed_at` is `index + width`, the first bar at which
    the pivot may be used.
    """

    index: int
    price: float
    kind: Literal["high", "low"]
    confirmed_at: int


@dataclass(frozen=True)
class Swing:
    """A ZigZag swing point on closes; `confirmed_at` is None for the tentative extreme."""

    index: int
    price: float
    kind: Literal["high", "low"]
    confirmed_at: int | None


@dataclass(frozen=True)
class ZigZag:
    """ZigZag result: confirmed swings (ascending) and the tentative last extreme, if any."""

    confirmed: tuple[Swing, ...]
    tentative: Swing | None


@dataclass(frozen=True)
class WeeklyBars:
    """Weekly OHLCV arrays; `week_index[i]` is the weekly bar that contains daily bar i."""

    week_ending: DateArray
    open: FloatArray
    high: FloatArray
    low: FloatArray
    close: FloatArray
    volume: FloatArray
    sessions: IntArray
    week_index: IntArray


def _check_window(n: int, minimum: int = 1, name: str = "window n") -> None:
    if n < minimum:
        msg = f"{name} must be >= {minimum}, got {n}"
        raise ValueError(msg)


def _same_length(*arrays: NDArray[np.generic]) -> None:
    if len({len(a) for a in arrays}) > 1:
        msg = "input arrays must have the same length"
        raise ValueError(msg)


def _windows(x: FloatArray, n: int) -> NDArray[np.float64] | None:
    """Trailing windows, one row per bar from index n-1; None when the input is shorter."""
    if len(x) < n:
        return None
    return sliding_window_view(x, n)


def _rolling(x: FloatArray, n: int, reducer: str) -> FloatArray:
    out = np.full(len(x), np.nan, dtype=np.float64)
    w = _windows(x, n)
    if w is not None:
        out[n - 1 :] = getattr(w, reducer)(axis=1)
    return out


def sma(x: FloatArray, n: int) -> FloatArray:
    """Simple moving average over the trailing n bars (bar t included).

    Warm-up: NaN for the first n-1 bars. Lag: (n-1)/2 bars.
    """
    _check_window(n)
    return _rolling(x, n, "mean")


def stdev(x: FloatArray, n: int) -> FloatArray:
    """Population standard deviation (ddof=0) over the trailing n bars.

    Warm-up: NaN for the first n-1 bars. Population, not sample, matching TradingView `ta.stdev`
    and the Bollinger convention (PRD A-06).
    """
    _check_window(n)
    return _rolling(x, n, "std")


def _recursive(x: FloatArray, n: int, alpha: float) -> FloatArray:
    """`y = prev + alpha * (x - prev)` seeded with the SMA of the first n non-NaN values."""
    out = np.full(len(x), np.nan, dtype=np.float64)
    valid = np.flatnonzero(~np.isnan(x))
    if len(valid) == 0:
        return out
    seed_at = int(valid[0]) + n - 1
    if seed_at >= len(x):
        return out
    prev = float(np.mean(x[valid[0] : seed_at + 1]))
    out[seed_at] = prev
    values = x.tolist()
    for i in range(seed_at + 1, len(x)):
        prev += alpha * (values[i] - prev)
        out[i] = prev
    return out


def ema(x: FloatArray, n: int) -> FloatArray:
    """Exponential moving average, alpha = 2 / (n + 1), seeded with the SMA of the first n values.

    Warm-up: NaN before index n-1 (the seed bar); later NaN inputs poison the rest.
    """
    _check_window(n)
    return _recursive(x, n, 2.0 / (n + 1))


def rma(x: FloatArray, n: int) -> FloatArray:
    """Wilder moving average, `(prev * (n - 1) + x) / n` (alpha = 1 / n), seeded with the SMA.

    Warm-up: NaN before index n-1 (the seed bar); later NaN inputs poison the rest.
    """
    _check_window(n)
    return _recursive(x, n, 1.0 / n)


def true_range(high: FloatArray, low: FloatArray, close: FloatArray) -> FloatArray:
    """True range: max(high - low, |high - prev close|, |low - prev close|).

    The first bar has no previous close, so it is `high - low`. No warm-up NaN.
    """
    _same_length(high, low, close)
    out = high - low
    if len(out) > 1:
        prev = close[:-1]
        out[1:] = np.maximum(out[1:], np.maximum(np.abs(high[1:] - prev), np.abs(low[1:] - prev)))
    return out


def atr(high: FloatArray, low: FloatArray, close: FloatArray, n: int = 14) -> FloatArray:
    """Average true range: the Wilder RMA of the true range.

    Warm-up: NaN before index n-1 (first value is the mean of the first n true ranges).
    """
    return rma(true_range(high, low, close), n)


def rsi(close: FloatArray, n: int = 14) -> FloatArray:
    """Wilder RSI: 100 - 100 / (1 + RMA(gains) / RMA(losses)).

    Changes start at index 1, so the first value is at index n (NaN before). All gains in the
    window give 100, all losses give 0. A window with no change at all (flat) has no direction
    and is defined as 50 (PRD A-16). Values are always within [0, 100].
    """
    _check_window(n)
    out = np.full(len(close), np.nan, dtype=np.float64)
    if len(close) < 2:
        return out
    change = np.diff(close)
    gain = rma(np.maximum(change, 0.0), n)
    loss = rma(np.maximum(-change, 0.0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        value = 100.0 - 100.0 / (1.0 + gain / loss)
    value = np.where(loss == 0.0, np.where(gain == 0.0, 50.0, 100.0), value)
    out[1:] = np.where(np.isnan(gain) | np.isnan(loss), np.nan, value)
    return out


def obv(close: FloatArray, volume: FloatArray) -> FloatArray:
    """On-balance volume: cumulative volume signed by the close-to-close direction.

    The first bar has no previous close and contributes 0, so OBV starts at 0. A flat close adds
    nothing. No warm-up NaN.
    """
    _same_length(close, volume)
    if len(close) == 0:
        return np.zeros(0, dtype=np.float64)
    signed = np.zeros(len(close), dtype=np.float64)
    signed[1:] = np.sign(np.diff(close)) * volume[1:]
    return np.cumsum(signed)


def percentile_rank(x: FloatArray, n: int) -> FloatArray:
    """Percentile rank of x[t] within the trailing window of n bars ending at t.

    Definition (PRD A-16): 100 * (number of the n-1 earlier bars in the window that are strictly
    below x[t]) / (n - 1). The result is in [0, 100]; ties do not count as below, so a constant
    series ranks 0. Warm-up: NaN for the first n-1 bars. Requires n >= 2.
    """
    _check_window(n, 2)
    out = np.full(len(x), np.nan, dtype=np.float64)
    w = _windows(x, n)
    if w is not None:
        below = (w[:, :-1] < w[:, -1:]).sum(axis=1)
        out[n - 1 :] = np.where(np.isnan(w).any(axis=1), np.nan, 100.0 * below / (n - 1))
    return out


def linreg_slope(x: FloatArray, n: int) -> FloatArray:
    """Least-squares slope per bar over the trailing n bars (x-axis 0..n-1).

    Warm-up: NaN for the first n-1 bars. Requires n >= 2.
    """
    _check_window(n, 2)
    out = np.full(len(x), np.nan, dtype=np.float64)
    w = _windows(x, n)
    if w is not None:
        centered = np.arange(n, dtype=np.float64) - (n - 1) / 2.0
        out[n - 1 :] = w @ centered / float(centered @ centered)
    return out


def pivot_confirmation_bar(index: int, width: int) -> int:
    """The first bar at which a pivot at `index` is known: `index + width`."""
    return index + width


def pivot_masks(high: FloatArray, low: FloatArray, width: int = 5) -> tuple[BoolArray, BoolArray]:
    """Boolean arrays (pivot highs, pivot lows) of confirmed pivots, marked at the pivot bar.

    A pivot low at p has a low strictly lower than the `width` lows on each side; a pivot high is
    the mirror. Only bars with `width <= p <= len - 1 - width` can be marked, so a pivot is never
    reported fewer than `width` bars from the end. The mark sits at p but is only knowable at
    `pivot_confirmation_bar(p, width)`; consumers at bar t must ignore marks with p + width > t
    (they never appear in input truncated at t).
    """
    _check_window(width, name="pivot width")
    _same_length(high, low)
    n = len(high)
    hi_mask = np.zeros(n, dtype=np.bool_)
    lo_mask = np.zeros(n, dtype=np.bool_)
    if n < 2 * width + 1:
        return hi_mask, lo_mask
    span = 2 * width + 1
    hw = sliding_window_view(high, span)
    lw = sliding_window_view(low, span)
    centre_hi = hw[:, width : width + 1]
    centre_lo = lw[:, width : width + 1]
    side = np.arange(span) != width
    hi_mask[width : n - width] = (centre_hi > hw[:, side]).all(axis=1)
    lo_mask[width : n - width] = (centre_lo < lw[:, side]).all(axis=1)
    return hi_mask, lo_mask


def pivots(high: FloatArray, low: FloatArray, width: int = 5) -> list[Pivot]:
    """Confirmed pivots as records sorted by bar index (a high before a low on the same bar)."""
    hi_mask, lo_mask = pivot_masks(high, low, width)
    found = [
        Pivot(int(i), float(high[i]), "high", pivot_confirmation_bar(int(i), width))
        for i in np.flatnonzero(hi_mask)
    ]
    found += [
        Pivot(int(i), float(low[i]), "low", pivot_confirmation_bar(int(i), width))
        for i in np.flatnonzero(lo_mask)
    ]
    return sorted(found, key=lambda pv: (pv.index, pv.kind != "high"))


def zigzag_threshold(
    atr: FloatArray, close: FloatArray, min_pct: float = 0.08, atr_mult: float = 3.0
) -> FloatArray:
    """ZigZag reversal threshold as a fraction: max(min_pct, atr_mult * atr / close).

    `atr` is the ATR(14) array. While ATR is NaN (warm-up) the floor `min_pct` applies.
    """
    _same_length(atr, close)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.fmax(min_pct, atr_mult * atr / close)


def zigzag(close: FloatArray, threshold: float | FloatArray) -> ZigZag:  # noqa: PLR0912
    """ZigZag swing detection on closes with a reversal threshold fraction.

    A swing extreme is confirmed on the first bar whose close reverses from it by at least
    `threshold` (a fraction, or one value per bar; the value at the reversal bar is used, so there
    is no look-ahead). The first swing is the start extreme that the first reversal confirms, and
    `Swing.confirmed_at` is the reversal bar. The current running extreme is returned separately
    as `tentative` (it may still move) and is None until a first direction is established.
    Bars with a NaN close or NaN threshold are skipped.
    """
    th = np.full(len(close), threshold, dtype=np.float64) if np.isscalar(threshold) else threshold
    if len(th) != len(close):
        msg = "threshold array must have the same length as close"
        raise ValueError(msg)
    confirmed: list[Swing] = []
    trend = 0  # 0 unknown, +1 tracking a high, -1 tracking a low
    hi_i = lo_i = -1
    hi_p = lo_p = 0.0
    for t in range(len(close)):
        c = float(close[t])
        r = float(th[t])
        if np.isnan(c) or np.isnan(r):
            continue
        if hi_i < 0:
            hi_i = lo_i = t
            hi_p = lo_p = c
            continue
        if trend == 0:
            hi_i, hi_p = (t, c) if c > hi_p else (hi_i, hi_p)
            lo_i, lo_p = (t, c) if c < lo_p else (lo_i, lo_p)
            if c <= hi_p * (1.0 - r):
                confirmed.append(Swing(hi_i, hi_p, "high", t))
                trend, lo_i, lo_p = -1, t, c
            elif c >= lo_p * (1.0 + r):
                confirmed.append(Swing(lo_i, lo_p, "low", t))
                trend, hi_i, hi_p = 1, t, c
        elif trend > 0:
            if c > hi_p:
                hi_i, hi_p = t, c
            elif c <= hi_p * (1.0 - r):
                confirmed.append(Swing(hi_i, hi_p, "high", t))
                trend, lo_i, lo_p = -1, t, c
        elif c < lo_p:
            lo_i, lo_p = t, c
        elif c >= lo_p * (1.0 + r):
            confirmed.append(Swing(lo_i, lo_p, "low", t))
            trend, hi_i, hi_p = 1, t, c
    tentative = None
    if trend > 0:
        tentative = Swing(hi_i, hi_p, "high", None)
    elif trend < 0:
        tentative = Swing(lo_i, lo_p, "low", None)
    return ZigZag(tuple(confirmed), tentative)


def resample_weekly(  # noqa: PLR0913, PLR0917
    dates: DateArray,
    open_: FloatArray,
    high: FloatArray,
    low: FloatArray,
    close: FloatArray,
    volume: FloatArray,
) -> WeeklyBars:
    """Resample daily bars to weekly bars (ADR-033), same semantics as `data.resample`.

    `dates` is datetime64[D], strictly ascending. A week is the ISO week (Monday to Sunday); the
    weekly bar is labeled with the last session present in it, so a holiday Friday labels the
    Thursday. The current partial week is included only through the last bar supplied. Weekly
    open is the first open, high the max, low the min, close the last close, volume the sum.
    `week_index[i]` is the weekly bar containing daily bar i.
    """
    _same_length(dates, open_, high, low, close, volume)
    days = dates.astype("datetime64[D]").astype(np.int64)
    if len(days) > 1 and not (np.diff(days) > 0).all():
        msg = "dates must be strictly ascending"
        raise ValueError(msg)
    if len(days) == 0:
        return WeeklyBars(
            dates.astype("datetime64[D]"),
            open_.copy(),
            high.copy(),
            low.copy(),
            close.copy(),
            volume.copy(),
            np.zeros(0, dtype=np.int64),
            np.zeros(0, dtype=np.int64),
        )
    # 1970-01-01 was a Thursday, so (day + 3) % 7 is the weekday with Monday = 0.
    monday = days - (days + 3) % 7
    new_week = np.r_[True, np.diff(monday) != 0]
    starts = np.flatnonzero(new_week)
    ends = np.r_[starts[1:], len(days)] - 1
    return WeeklyBars(
        week_ending=dates[ends].astype("datetime64[D]"),
        open=open_[starts],
        high=np.maximum.reduceat(high, starts),
        low=np.minimum.reduceat(low, starts),
        close=close[ends],
        volume=np.add.reduceat(volume, starts),
        sessions=(ends - starts + 1).astype(np.int64),
        week_index=(np.cumsum(new_week) - 1).astype(np.int64),
    )
