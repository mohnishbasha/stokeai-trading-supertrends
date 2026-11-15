# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Indicator primitives (stub; implementation follows the failing tests)."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
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
    """A confirmed pivot."""

    index: int
    price: float
    kind: Literal["high", "low"]
    confirmed_at: int


@dataclass(frozen=True)
class Swing:
    """A ZigZag swing point."""

    index: int
    price: float
    kind: Literal["high", "low"]
    confirmed_at: int | None


@dataclass(frozen=True)
class ZigZag:
    """ZigZag result."""

    confirmed: tuple[Swing, ...]
    tentative: Swing | None


@dataclass(frozen=True)
class WeeklyBars:
    """Weekly arrays."""

    week_ending: DateArray
    open: FloatArray
    high: FloatArray
    low: FloatArray
    close: FloatArray
    volume: FloatArray
    sessions: IntArray
    week_index: IntArray


def sma(x: FloatArray, n: int) -> FloatArray:
    raise NotImplementedError


def ema(x: FloatArray, n: int) -> FloatArray:
    raise NotImplementedError


def rma(x: FloatArray, n: int) -> FloatArray:
    raise NotImplementedError


def stdev(x: FloatArray, n: int) -> FloatArray:
    raise NotImplementedError


def true_range(high: FloatArray, low: FloatArray, close: FloatArray) -> FloatArray:
    raise NotImplementedError


def atr(high: FloatArray, low: FloatArray, close: FloatArray, n: int = 14) -> FloatArray:
    raise NotImplementedError


def rsi(close: FloatArray, n: int = 14) -> FloatArray:
    raise NotImplementedError


def obv(close: FloatArray, volume: FloatArray) -> FloatArray:
    raise NotImplementedError


def percentile_rank(x: FloatArray, n: int) -> FloatArray:
    raise NotImplementedError


def linreg_slope(x: FloatArray, n: int) -> FloatArray:
    raise NotImplementedError


def pivot_confirmation_bar(index: int, width: int) -> int:
    raise NotImplementedError


def pivot_masks(high: FloatArray, low: FloatArray, width: int = 5) -> tuple[BoolArray, BoolArray]:
    raise NotImplementedError


def pivots(high: FloatArray, low: FloatArray, width: int = 5) -> list[Pivot]:
    raise NotImplementedError


def zigzag_threshold(
    atr: FloatArray, close: FloatArray, min_pct: float = 0.08, atr_mult: float = 3.0
) -> FloatArray:
    raise NotImplementedError


def zigzag(close: FloatArray, threshold: float | FloatArray) -> ZigZag:
    raise NotImplementedError


def resample_weekly(  # noqa: PLR0913, PLR0917
    dates: DateArray,
    open_: FloatArray,
    high: FloatArray,
    low: FloatArray,
    close: FloatArray,
    volume: FloatArray,
) -> WeeklyBars:
    raise NotImplementedError
