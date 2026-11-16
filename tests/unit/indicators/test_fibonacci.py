# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Fibonacci legs and levels (TS-IND-100 to TS-IND-107). Expected values are derived by hand."""

import numpy as np
from numpy.typing import NDArray

from supertrends.indicators import fibonacci as fib

TOL = 1e-6


def piecewise(*points: tuple[int, float]) -> NDArray[np.float64]:
    """Linear interpolation through (index, price) knots; one value per integer index."""
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return np.interp(np.arange(xs[-1] + 1), xs, ys).astype(np.float64)


def leg_of(close: NDArray[np.float64], **kwargs: int) -> fib.FibLeg | None:
    return fib.fib_leg(close, close, close, **kwargs)


# A=100 (bar 0), B=150 (bar 30), pullback to 125 (bar 45). Slope <= 1.7 per bar so
# 3 * ATR% is about 5% and the 8% floor applies; the pullback is 16.7% so B confirms.
UP = piecewise((0, 100.0), (30, 150.0), (45, 125.0))
DOWN = piecewise((0, 150.0), (30, 100.0), (45, 125.0))


def test_leg_select_most_recent_completed_leg_over_lookback() -> None:
    """TS-IND-100: latest completed leg A to B, restricted to the lookback window."""
    close = piecewise((0, 100.0), (30, 150.0), (60, 100.0), (90, 160.0), (110, 120.0))
    # Full window: swings low 100 @0, high 150 @30, low 100 @60, high 160 @90 (confirmed @97).
    full = leg_of(close, lookback=120)
    assert full is not None
    assert (full.a_index, full.a_price, full.b_index, full.b_price) == (60, 100.0, 90, 160.0)
    assert full.direction == 1
    # Last 50 bars start at index 61 (close 102): that start extreme is the low A, B is 160 @90.
    short = leg_of(close, lookback=50)
    assert short is not None
    assert (short.a_index, short.a_price) == (61, 102.0)
    assert (short.b_index, short.b_price) == (90, 160.0)


def test_up_leg_pullback_61_8_within_1e6() -> None:
    """TS-IND-101: 61.8 level of the 100 -> 150 leg is 150 - 0.618 * 50 = 119.1."""
    leg = leg_of(UP)
    assert leg is not None
    assert leg.direction == 1
    assert abs(leg.retracement(0.618) - 119.1) <= TOL


def test_all_five_retracements_measured_from_b_toward_a() -> None:
    """TS-IND-102: B + (A - B) * r for r in 23.6, 38.2, 50, 61.8, 78.6 percent."""
    leg = leg_of(UP)
    assert leg is not None
    # 150 - 50 * r: 138.2, 130.9, 125.0, 119.1, 110.7
    expected = [138.2, 130.9, 125.0, 119.1, 110.7]
    assert fib.RETRACEMENT_RATIOS == (0.236, 0.382, 0.5, 0.618, 0.786)
    assert len(leg.retracements) == 5
    for got, want in zip(leg.retracements, expected, strict=True):
        assert abs(got - want) <= TOL


def test_extensions_127_2_and_161_8() -> None:
    """TS-IND-103: extensions A + ratio * (B - A): 100 + 63.6 and 100 + 80.9."""
    leg = leg_of(UP)
    assert leg is not None
    assert fib.EXTENSION_RATIOS == (1.272, 1.618)
    assert abs(leg.extension(1.272) - 163.6) <= TOL
    assert abs(leg.extension(1.618) - 180.9) <= TOL
    assert len(leg.extensions) == 2


def test_down_leg_mirrored() -> None:
    """TS-IND-104: A=150 high, B=100 low; 61.8 is 100 + 50 * 0.618; extensions go below B."""
    leg = leg_of(DOWN)
    assert leg is not None
    assert leg.direction == -1
    assert (leg.a_price, leg.b_price) == (150.0, 100.0)
    assert abs(leg.retracement(0.618) - 130.9) <= TOL
    assert abs(leg.retracement(0.236) - 111.8) <= TOL
    assert abs(leg.extension(1.272) - 86.4) <= TOL
    assert abs(leg.extension(1.618) - 69.1) <= TOL


def test_no_qualifying_leg_returns_none() -> None:
    """TS-IND-105: flat, one-swing, and short series have no completed leg."""
    assert leg_of(np.full(60, 100.0)) is None
    # Only one confirmed swing (low at 0, then a single 8%+ rise and no reversal).
    assert leg_of(piecewise((0, 100.0), (30, 150.0))) is None
    assert leg_of(np.array([100.0, 110.0])) is None
    assert leg_of(np.array([], dtype=np.float64)) is None


def test_near_and_holding_helpers() -> None:
    """TS-IND-106: near is |close - level| <= k * atr; holding follows the Factor 6 formula."""
    assert fib.near(100.5, 100.0, 1.0)
    assert fib.near(99.5, 100.0, 1.0)
    assert not fib.near(100.51, 100.0, 1.0)
    assert fib.near(101.0, 100.0, 1.0, k=1.0)
    # Up leg: close rose and low >= level - 0.5 atr.
    assert fib.holding(1, 101.0, 100.0, 99.5, 100.0, 1.0)
    assert not fib.holding(1, 101.0, 100.0, 99.4, 100.0, 1.0)
    assert not fib.holding(1, 100.0, 101.0, 100.0, 100.0, 1.0)
    # Down leg mirror: close fell and high <= level + 0.5 atr.
    assert fib.holding(-1, 99.0, 100.0, 100.5, 100.0, 1.0)
    assert not fib.holding(-1, 99.0, 100.0, 100.6, 100.0, 1.0)
    assert not fib.holding(-1, 100.0, 99.0, 100.0, 100.0, 1.0)


def test_threshold_uses_3_atr_pct_when_above_8_percent() -> None:
    """TS-IND-107: wide daily ranges lift the threshold above the swings, so no leg qualifies."""
    close = piecewise((0, 100.0), (30, 150.0), (45, 125.0))
    assert leg_of(close) is not None
    # Same closes but daily range +-20 percent: atr% is about 40 percent, threshold 1.2 (120 %).
    wide = fib.fib_leg(close * 1.2, close * 0.8, close)
    assert wide is None
