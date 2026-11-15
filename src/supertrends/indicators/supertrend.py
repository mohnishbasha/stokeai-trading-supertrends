# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Supertrend (Signal Engine Specification, Factor 1). Stub: implementation follows."""

from dataclasses import dataclass

from supertrends.indicators.primitives import DateArray, FloatArray

__all__ = [
    "SupertrendResult",
    "bars_since_flip",
    "distance_atr",
    "supertrend_weekly_direction",
]


@dataclass(frozen=True)
class SupertrendResult:
    """Supertrend arrays."""

    line: FloatArray
    direction: FloatArray
    final_upper: FloatArray
    final_lower: FloatArray
    atr: FloatArray


def supertrend(
    high: FloatArray, low: FloatArray, close: FloatArray, atr_length: int = 10, factor: float = 3.0
) -> SupertrendResult:
    raise NotImplementedError


def bars_since_flip(direction: FloatArray) -> FloatArray:
    raise NotImplementedError


def distance_atr(close: FloatArray, line: FloatArray, atr: FloatArray) -> FloatArray:
    raise NotImplementedError


def supertrend_weekly_direction(  # noqa: PLR0913, PLR0917
    dates: DateArray,
    open_: FloatArray,
    high: FloatArray,
    low: FloatArray,
    close: FloatArray,
    volume: FloatArray,
    atr_length: int = 10,
    factor: float = 3.0,
) -> FloatArray:
    raise NotImplementedError
