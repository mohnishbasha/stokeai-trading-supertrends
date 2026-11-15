# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Estimated buy and sell volume flow (owned by S2-T07; BUILD_PROMPT Factor 10)."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "FlowQuality",
    "FlowResult",
    "TradesClassifier",
    "estimate_order_flow",
    "split_volume",
]

FloatArray = NDArray[np.float64]


class FlowQuality(StrEnum):
    """Data quality of the order flow estimate."""

    INTRADAY = "intraday"
    DAILY_ESTIMATE = "daily_estimate"
    TRADES = "trades"


class TradesClassifier(Protocol):
    """Plug-in for tick-rule classification of trade prints (not implemented in v1)."""

    def delta_pct(self, sessions: NDArray[np.datetime64]) -> FloatArray:
        """Per-session delta percent for the given session dates; NaN where unavailable."""
        ...


@dataclass(frozen=True)
class FlowResult:
    """Order flow per daily session plus the 10-session summary."""

    sessions: NDArray[np.datetime64]
    buy: FloatArray
    sell: FloatArray
    delta: FloatArray
    delta_pct: FloatArray
    delta_pct_10: float
    quality: FlowQuality
    daily_fallback: bool
    intraday_sessions: int


def split_volume(
    high: FloatArray, low: FloatArray, close: FloatArray, volume: FloatArray, prev_close: FloatArray
) -> tuple[FloatArray, FloatArray]:
    """Split each bar's volume into estimated (buy, sell)."""
    raise NotImplementedError


def estimate_order_flow(  # noqa: PLR0913, PLR0917
    sessions: NDArray[np.datetime64],
    d_high: FloatArray,
    d_low: FloatArray,
    d_close: FloatArray,
    d_volume: FloatArray,
    bar_start: NDArray[np.datetime64] | None = None,
    high: FloatArray | None = None,
    low: FloatArray | None = None,
    close: FloatArray | None = None,
    volume: FloatArray | None = None,
    trades: TradesClassifier | None = None,
    window: int = 10,
    min_intraday_sessions: int = 8,
) -> FlowResult:
    """Estimate order flow per session and the mean delta percent over the last 10 sessions."""
    raise NotImplementedError
