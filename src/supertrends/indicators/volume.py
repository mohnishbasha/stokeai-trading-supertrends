# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Volume indicators (owned by S2-T07; BUILD_PROMPT Factor 9, relative volume, Factor 10 evidence).

Inputs are 1-D float64 arrays of equal length; outputs are float64 arrays of the same length with
NaN during warm-up. A zero denominator gives NaN, never a silent zero or infinity.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from supertrends.indicators.primitives import ema, linreg_slope, obv, sma

__all__ = [
    "AccDistDays",
    "accumulation_distribution_days",
    "cmf",
    "obv_slope_sign",
    "relative_volume",
    "volume_oscillator",
]

FloatArray = NDArray[np.float64]


def _check_lengths(*arrays: FloatArray) -> None:
    if len({len(a) for a in arrays}) > 1:
        msg = "input arrays must have the same length"
        raise ValueError(msg)


@dataclass(frozen=True)
class AccDistDays:
    """Counts of accumulation and distribution days in the trailing window, one value per bar."""

    accumulation: FloatArray
    distribution: FloatArray


def volume_oscillator(volume: FloatArray, short: int = 5, long: int = 10) -> FloatArray:
    """`100 * (EMA_short - EMA_long) / EMA_long`.

    Warm-up: NaN for the first `long - 1` bars. NaN where EMA_long is 0.
    """
    if short < 1 or long < 1:
        msg = f"window must be >= 1, got short={short}, long={long}"
        raise ValueError(msg)
    e_long = ema(volume, long)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 100.0 * (ema(volume, short) - e_long) / e_long
    return np.where(e_long == 0.0, np.nan, out)


def relative_volume(volume: FloatArray, n: int = 20) -> FloatArray:
    """`volume / SMA_n(volume)` (the SMA includes the current bar).

    Warm-up: NaN for the first `n - 1` bars. NaN where the SMA is 0.
    """
    avg = sma(volume, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = volume / avg
    return np.where(avg == 0.0, np.nan, out)


def obv_slope_sign(close: FloatArray, volume: FloatArray, n: int = 20) -> FloatArray:
    """Sign (+1, 0, -1) of the least-squares slope of OBV over the trailing n bars.

    Warm-up: NaN for the first `n - 1` bars.
    """
    _check_lengths(close, volume)
    slope = linreg_slope(obv(close, volume), n)
    return np.sign(slope)


def cmf(
    high: FloatArray, low: FloatArray, close: FloatArray, volume: FloatArray, n: int = 20
) -> FloatArray:
    """Chaikin Money Flow: sum of money-flow volume over n bars divided by sum of volume.

    The money-flow multiplier is `((close - low) - (high - close)) / (high - low)`, and 0 on a
    zero-range bar. Warm-up: NaN for the first `n - 1` bars. NaN where the volume sum is 0.
    """
    _check_lengths(high, low, close, volume)
    rng = high - low
    with np.errstate(divide="ignore", invalid="ignore"):
        mfm = np.where(rng > 0.0, ((close - low) - (high - close)) / rng, 0.0)
    total = sma(volume, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = sma(mfm * volume, n) / total
    return np.where(total == 0.0, np.nan, out)


def accumulation_distribution_days(
    close: FloatArray,
    volume: FloatArray,
    window: int = 20,
    rel_vol_n: int = 20,
    threshold: float = 1.5,
) -> AccDistDays:
    """Count accumulation and distribution days over the last `window` sessions.

    Accumulation day: close above the previous close with relative volume >= threshold.
    Distribution day: close below the previous close with relative volume >= threshold.
    Warm-up: NaN until every bar in the window has a relative volume, that is for the first
    `rel_vol_n + window - 2` bars.
    """
    _check_lengths(close, volume)
    rel = relative_volume(volume, rel_vol_n)
    change = np.zeros(len(close), dtype=np.float64)
    change[1:] = np.diff(close)
    with np.errstate(invalid="ignore"):
        heavy = rel >= threshold  # NaN compares False
        acc = (heavy & (change > 0.0)).astype(np.float64)
        dist = (heavy & (change < 0.0)).astype(np.float64)
    first_valid = rel_vol_n + window - 2
    out = []
    for flags in (acc, dist):
        counts = sma(flags, window) * window
        counts[:first_valid] = np.nan
        out.append(np.round(counts))
    return AccDistDays(accumulation=out[0], distribution=out[1])
