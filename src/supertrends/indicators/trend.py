# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Trend indicators: SMA stack, slope, crosses, ADX (owned by S2-T03; Factors 2 and 3)."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

__all__ = ["Adx", "Cross", "SmaStack", "adx", "cross_events", "last_cross", "sma_slope", "sma_stack"]


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


def sma_stack(close: FloatArray, short: int = 20, mid: int = 50, long: int = 200) -> SmaStack:
    raise NotImplementedError


def sma_slope(values: FloatArray, bars: int = 5) -> FloatArray:
    raise NotImplementedError


def cross_events(a: FloatArray, b: FloatArray) -> IntArray:
    raise NotImplementedError


def last_cross(a: FloatArray, b: FloatArray, lookback: int) -> Cross | None:
    raise NotImplementedError


def adx(high: FloatArray, low: FloatArray, close: FloatArray, n: int = 14) -> Adx:
    raise NotImplementedError
