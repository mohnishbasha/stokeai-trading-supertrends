# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Divergence detection on confirmed pivots (Signal Engine Specification, Factor 4; S2-T04).

Regular and hidden, bullish and bearish divergences between price pivots and an oscillator
(RSI, MACD histogram, OBV), on daily bars (pivot width 5) and weekly bars (pivot width 3).

Rules (BUILD_PROMPT Factor 4):

* Only confirmed pivots are used (NFR-007). A pivot at bar p is usable at bar t only if
  `p + width <= t`, so a divergence is known `width` bars after its second pivot.
* The two most recent confirmed pivot lows are compared (bullish), and separately the two most
  recent confirmed pivot highs (bearish). Both pivots must lie in the last `lookback` bars
  (`t - p1 <= lookback - 1`); if the older one is outside the window there is no divergence.
* Only divergences whose second pivot is recent count: `t - p2 <= recency`. The distance is
  measured to the pivot bar p2 (the literal reading), not to the confirmation bar.
* Price is read at the pivot bar (low for pivot lows, high for pivot highs) and the oscillator
  value at the same bar. Equal prices or equal oscillator values are not a divergence.
  A pivot whose oscillator value is NaN (warm-up) cannot take part in a comparison.

Lag: `width` bars. Pivot masks depend only on bars `p - width .. p + width`, so computing them on
the full array and activating each pair at `p2 + width` is identical to truncating the input at
every bar (verified by the property test).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np  # noqa: F401

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from supertrends.indicators.primitives import WeeklyBars

    FloatArray = NDArray[np.float64]
    BoolArray = NDArray[np.bool_]

__all__ = [
    "Divergence",
    "DivergenceSeries",
    "detect_all_divergences",
    "detect_divergences",
    "detect_weekly_divergences",
    "divergence_records",
    "divergence_series",
]

DAILY_WIDTH = 5
WEEKLY_WIDTH = 3
LOOKBACK = 60
RECENCY = 15

Kind = Literal["regular", "hidden"]
Side = Literal["bullish", "bearish"]
Timeframe = Literal["daily", "weekly"]


@dataclass(frozen=True)
class Divergence:
    """One divergence between two confirmed pivots (indexes are bars of the input timeframe).

    `p1` is the older pivot, `p2` the newer. `price1/price2` are the pivot low (bullish) or
    pivot high (bearish); `osc1/osc2` the oscillator at the same bars. `confirmed_at` is
    `p2 + width`, the first bar at which the divergence is known.
    """

    kind: Kind
    side: Side
    oscillator: str
    timeframe: Timeframe
    p1: int
    p2: int
    price1: float
    price2: float
    osc1: float
    osc2: float
    confirmed_at: int


@dataclass(frozen=True)
class DivergenceSeries:
    """Per-bar flags, as of each bar, that an active divergence of each type exists."""

    regular_bullish: BoolArray
    regular_bearish: BoolArray
    hidden_bullish: BoolArray
    hidden_bearish: BoolArray


def _macd_hist(close: FloatArray) -> FloatArray:
    raise NotImplementedError


def divergence_records(  # noqa: PLR0913
    high: FloatArray,
    low: FloatArray,
    osc: FloatArray,
    *,
    oscillator: str,
    timeframe: Timeframe = "daily",
    width: int = DAILY_WIDTH,
    lookback: int = LOOKBACK,
    recency: int = RECENCY,
) -> list[Divergence]:
    raise NotImplementedError


def detect_divergences(  # noqa: PLR0913
    high: FloatArray,
    low: FloatArray,
    osc: FloatArray,
    *,
    oscillator: str,
    timeframe: Timeframe = "daily",
    width: int = DAILY_WIDTH,
    lookback: int = LOOKBACK,
    recency: int = RECENCY,
    as_of: int | None = None,
) -> list[Divergence]:
    raise NotImplementedError


def divergence_series(
    high: FloatArray,
    low: FloatArray,
    osc: FloatArray,
    *,
    width: int = DAILY_WIDTH,
    lookback: int = LOOKBACK,
    recency: int = RECENCY,
) -> DivergenceSeries:
    raise NotImplementedError


def detect_all_divergences(  # noqa: PLR0913
    high: FloatArray,
    low: FloatArray,
    close: FloatArray,
    volume: FloatArray,
    *,
    timeframe: Timeframe = "daily",
    width: int = DAILY_WIDTH,
    lookback: int = LOOKBACK,
    recency: int = RECENCY,
    as_of: int | None = None,
) -> list[Divergence]:
    raise NotImplementedError


def detect_weekly_divergences(
    weekly: WeeklyBars,
    *,
    lookback: int = LOOKBACK,
    recency: int = RECENCY,
    as_of: int | None = None,
) -> list[Divergence]:
    raise NotImplementedError
