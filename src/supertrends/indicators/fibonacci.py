# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Fibonacci retracements and extensions on ZigZag legs (owned by S2-T06; Factor 6).

Spec: BUILD_PROMPT "Factor 6: Fibonacci retracement". ZigZag runs on daily closes over the last
`lookback` (120) bars with reversal threshold `max(8%, 3 * ATR%)`, `ATR% = atr14 / close` taken
at the as-of (last) bar. The leg is A -> B where B is the last confirmed swing and A the swing
before it. Retracements are measured from B back toward A; extensions project from A through B
(`A + ratio * (B - A)`).

`fib_leg` is an as-of-last-bar function: to evaluate bar t, a caller passes `bars[:t+1]`. A swing
is confirmed only by a later reversal close, so the leg lags the extreme by the reversal.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from supertrends.indicators.primitives import atr as _atr
from supertrends.indicators.primitives import zigzag, zigzag_threshold

FloatArray = NDArray[np.float64]

__all__ = [
    "EXTENSION_RATIOS",
    "RETRACEMENT_RATIOS",
    "FibLeg",
    "fib_leg",
    "holding",
    "near",
]

RETRACEMENT_RATIOS: tuple[float, ...] = (0.236, 0.382, 0.5, 0.618, 0.786)
EXTENSION_RATIOS: tuple[float, ...] = (1.272, 1.618)


@dataclass(frozen=True)
class FibLeg:
    """A completed ZigZag leg A -> B. `direction` is +1 for an up leg (A low, B high), -1 down.

    Indices refer to the arrays passed to `fib_leg`.
    """

    a_index: int
    a_price: float
    b_index: int
    b_price: float
    direction: int

    def retracement(self, ratio: float) -> float:
        """Price `ratio` of the way from B back toward A: `B + (A - B) * ratio`."""
        return self.b_price + (self.a_price - self.b_price) * ratio

    def extension(self, ratio: float) -> float:
        """Extension price `A + ratio * (B - A)`, beyond B in the direction of the leg."""
        return self.a_price + (self.b_price - self.a_price) * ratio

    @property
    def retracements(self) -> tuple[float, ...]:
        """Retracement prices aligned with `RETRACEMENT_RATIOS`."""
        return tuple(self.retracement(r) for r in RETRACEMENT_RATIOS)

    @property
    def extensions(self) -> tuple[float, ...]:
        """Extension prices aligned with `EXTENSION_RATIOS`."""
        return tuple(self.extension(r) for r in EXTENSION_RATIOS)


def fib_leg(  # noqa: PLR0913, PLR0917
    high: FloatArray,
    low: FloatArray,
    close: FloatArray,
    lookback: int = 120,
    min_pct: float = 0.08,
    atr_mult: float = 3.0,
    atr_period: int = 14,
) -> FibLeg | None:
    """Most recent completed ZigZag leg over the last `lookback` closes, as of the last bar.

    The threshold is the single value `max(min_pct, atr_mult * ATR(atr_period) / close)` at the
    last bar (the 8% floor applies while ATR is in warm-up). Returns None when fewer than two
    swings are confirmed in the window (the factor treats that as quality `degraded`). Swing
    indices are relative to the full arrays. NaN closes are skipped by the ZigZag.
    """
    n = len(close)
    if n == 0:
        return None
    start = max(0, n - lookback)
    thr = float(zigzag_threshold(_atr(high, low, close, atr_period), close, min_pct, atr_mult)[-1])
    swings = zigzag(close[start:], thr).confirmed
    if len(swings) < 2:
        return None
    a, b = swings[-2], swings[-1]
    return FibLeg(
        a_index=start + a.index,
        a_price=a.price,
        b_index=start + b.index,
        b_price=b.price,
        direction=1 if b.kind == "high" else -1,
    )


def near(close: float, level: float, atr: float, k: float = 0.5) -> bool:
    """`|close - level| <= k * atr`."""
    return abs(close - level) <= k * atr


def holding(  # noqa: PLR0913, PLR0917
    direction: int,
    close: float,
    prev_close: float,
    extreme: float,
    level: float,
    atr: float,
    k: float = 0.5,
) -> bool:
    """Factor 6 `holding` test for a pullback to `level`.

    Up leg (`direction` +1; `extreme` is the bar's low): `close > prev_close` and
    `low >= level - k * atr`. Down leg (-1; `extreme` is the bar's high): the mirror,
    `close < prev_close` and `high <= level + k * atr`.
    """
    if direction > 0:
        return close > prev_close and extreme >= level - k * atr
    return close < prev_close and extreme <= level + k * atr
