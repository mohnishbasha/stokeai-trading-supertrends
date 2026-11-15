# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Mean-reversion indicators: Bollinger, %B, z-score (owned by S2-T05; Factor 5).

Spec: Signal Engine Specification, Factor 5 (mean reversion). Bollinger bands use the population
standard deviation of the closes (ddof=0), matching TradingView `ta.stdev` (PRD A-06).
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from supertrends.indicators.primitives import sma, stdev

__all__ = ["Bollinger", "bollinger", "pct_b", "zscore"]

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class Bollinger:
    """Bollinger bands: middle (SMA), upper, and lower, each the same length as the input."""

    middle: FloatArray
    upper: FloatArray
    lower: FloatArray


def bollinger(close: FloatArray, n: int = 20, k: float = 2.0) -> Bollinger:
    """Bollinger bands: SMA(n) +/- k * population stdev(n).

    Warm-up: NaN for the first n-1 bars. Lag follows the SMA, (n-1)/2 bars. NaN in the input
    makes every window containing it NaN.
    """
    raise NotImplementedError


def pct_b(close: FloatArray, n: int = 20, k: float = 2.0) -> FloatArray:
    """%B = (close - lower) / (upper - lower).

    Warm-up: NaN for the first n-1 bars. NaN where the bands have zero width (flat window).
    """
    raise NotImplementedError


def zscore(close: FloatArray, n: int = 20) -> FloatArray:
    """z = (close - SMA(n)) / population stdev(n).

    Warm-up: NaN for the first n-1 bars. NaN where the stdev is zero (flat window).
    """
    raise NotImplementedError
