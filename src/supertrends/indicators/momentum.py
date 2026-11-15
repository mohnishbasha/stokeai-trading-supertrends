# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Momentum indicators: MACD and related oscillators (owned by S2-T03; Factor 3)."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from supertrends.indicators.trend import Cross

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

__all__ = ["Macd", "hist_run", "macd", "macd_signal_cross", "macd_weekly"]


@dataclass(frozen=True)
class Macd:
    """MACD line, signal line, and histogram."""

    line: FloatArray
    signal: FloatArray
    hist: FloatArray


def macd(close: FloatArray, fast: int = 12, slow: int = 26, signal: int = 9) -> Macd:
    raise NotImplementedError


def macd_weekly(
    dates: NDArray[np.datetime64], close: FloatArray, fast: int = 12, slow: int = 26, signal: int = 9
) -> Macd:
    raise NotImplementedError


def macd_signal_cross(line: FloatArray, signal: FloatArray, lookback: int = 3) -> Cross | None:
    raise NotImplementedError


def hist_run(hist: FloatArray, bars: int = 3) -> IntArray:
    raise NotImplementedError
