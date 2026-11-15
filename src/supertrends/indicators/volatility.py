# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Volatility indicators: ATR%, HV20, ranks, squeeze (owned by S2-T05; Factor 8).

Spec: Signal Engine Specification, Factor 8 (volatility). Ranks are trailing-window percentile
ranks (`primitives.percentile_rank`), so the value at t never depends on later bars. Flags are
float arrays (1.0 true, 0.0 false, NaN while their inputs are in warm-up).
"""

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray

from supertrends.indicators.meanrev import bollinger
from supertrends.indicators.primitives import atr, percentile_rank, stdev

__all__ = [
    "atr_pct",
    "atr_pct_rank",
    "bandwidth",
    "bbw_rank",
    "expansion",
    "hv20",
    "squeeze",
]

FloatArray = NDArray[np.float64]


def _safe_div(num: FloatArray, den: FloatArray) -> FloatArray:
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(den > 0.0, num / den, np.nan)
    return np.asarray(out, dtype=np.float64)


def bandwidth(close: FloatArray, n: int = 20, k: float = 2.0) -> FloatArray:
    """Bollinger bandwidth (upper - lower) / SMA(n). Warm-up: NaN for the first n-1 bars."""
    bands = bollinger(close, n, k)
    return _safe_div(bands.upper - bands.lower, bands.middle)


def bbw_rank(close: FloatArray, n: int = 20, k: float = 2.0, rank_window: int = 126) -> FloatArray:
    """Percentile rank of bandwidth over the trailing rank_window bars (0 to 100).

    Warm-up: NaN until bandwidth has rank_window valid values, i.e. n + rank_window - 2 bars.
    """
    return percentile_rank(bandwidth(close, n, k), rank_window)


def atr_pct(high: FloatArray, low: FloatArray, close: FloatArray, n: int = 14) -> FloatArray:
    """ATR% = ATR(n) / close. Warm-up: NaN for the first n-1 bars."""
    return _safe_div(atr(high, low, close, n), close)


def atr_pct_rank(
    high: FloatArray,
    low: FloatArray,
    close: FloatArray,
    n: int = 14,
    rank_window: int = 252,
) -> FloatArray:
    """Percentile rank of ATR% over the trailing rank_window bars (0 to 100).

    Warm-up: NaN until ATR% has rank_window valid values, i.e. n + rank_window - 2 bars.
    """
    return percentile_rank(atr_pct(high, low, close, n), rank_window)


def hv20(close: FloatArray, n: int = 20, trading_days: int = 252) -> FloatArray:
    """Historical volatility: population stdev of n daily log returns * sqrt(trading_days).

    Population (ddof=0) for consistency with the z-score and Bollinger (PRD A-17). Warm-up: NaN
    for the first n bars (the first log return needs two closes). Non-positive closes give NaN.
    """
    ret = np.full(len(close), np.nan, dtype=np.float64)
    if len(close) > 1:
        with np.errstate(divide="ignore", invalid="ignore"):
            r = np.log(close[1:] / close[:-1])
        ret[1:] = np.where(np.isfinite(r), r, np.nan)
    return stdev(ret, n) * float(np.sqrt(trading_days))


def squeeze(rank: FloatArray, threshold: float = 15.0) -> FloatArray:
    """Squeeze flag: 1.0 when bbw_rank < threshold (strict), else 0.0; NaN where rank is NaN."""
    return np.where(np.isnan(rank), np.nan, (rank < threshold).astype(np.float64))


def expansion(
    rank: FloatArray, bbw: FloatArray, threshold: float = 85.0, bars: int = 3
) -> FloatArray:
    """Expansion flag: bbw_rank > threshold and bandwidth rising for `bars` bars.

    "Rising 3 bars" is read literally as 3 consecutive increases: bbw[t] > bbw[t-1] > bbw[t-2]
    > bbw[t-3] (PRD A-18). 1.0 or 0.0; NaN where rank or any needed bandwidth value is NaN.
    """
    if len(rank) != len(bbw):
        msg = "input arrays must have the same length"
        raise ValueError(msg)
    out = np.full(len(bbw), np.nan, dtype=np.float64)
    if len(bbw) > bars:
        w = sliding_window_view(bbw, bars + 1)
        rising = (np.diff(w, axis=1) > 0.0).all(axis=1)
        flag = ((rank[bars:] > threshold) & rising).astype(np.float64)
        missing = np.isnan(w).any(axis=1) | np.isnan(rank[bars:])
        out[bars:] = np.where(missing, np.nan, flag)
    return out
