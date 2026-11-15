# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Support and resistance levels (TS-IND-110 to TS-IND-119, TS-IND-220 to TS-IND-221).

Fixtures are a flat tape (high 101, low 99, close 100, volume 1000) with single-bar spikes in the
high (pivot highs) or low (pivot lows). Spikes sit at least 6 bars apart, so each is a strict
width-5 pivot and the flat bars are not pivots. Expected ATR comes from `atr_ref`, a plain-loop
Wilder ATR written here, not from the code under test.
"""

import numpy as np
from numpy.typing import NDArray

from supertrends.indicators import levels as lv

Arr = NDArray[np.float64]


def atr_ref(high: Arr, low: Arr, close: Arr, n: int = 14) -> float:
    """Wilder ATR at the last bar: seed = mean of first n true ranges, then recursive."""
    tr = [float(high[0] - low[0])]
    for i in range(1, len(high)):
        pc = float(close[i - 1])
        tr.append(max(high[i] - low[i], abs(high[i] - pc), abs(low[i] - pc)))
    a = sum(tr[:n]) / n
    for x in tr[n:]:
        a = (a * (n - 1) + x) / n
    return float(a)


def tape(
    n: int,
    up: dict[int, float] | None = None,
    down: dict[int, float] | None = None,
) -> tuple[Arr, Arr, Arr, Arr]:
    """Flat tape with high spikes `up` {bar: high} and low spikes `down` {bar: low}."""
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)
    volume = np.full(n, 1000.0)
    for i, price in (up or {}).items():
        high[i] = price
    for i, price in (down or {}).items():
        low[i] = price
    return high, low, close, volume


def weight(age: int) -> float:
    return 1.0 - 0.7 * age / 250.0


def run(
    arrays: tuple[Arr, Arr, Arr, Arr],
) -> lv.SupportResistance:
    result = lv.support_resistance(*arrays)
    assert result is not None
    return result


def pivot_levels(levels: tuple[lv.Level, ...]) -> list[lv.Level]:
    return sorted((x for x in levels if x.kind == "cluster"), key=lambda x: x.price)


def test_cluster_merges_pivots_within_half_atr() -> None:
    """TS-IND-110: pivots 0.5 apart merge (mean 110.25); a pivot 3.75 further stays separate."""
    arrays = tape(100, up={20: 110.0, 40: 110.5, 60: 114.0})
    tol = 0.5 * atr_ref(arrays[0], arrays[1], arrays[2])
    assert 0.5 <= tol < 3.5  # precondition: 110.0/110.5 merge, 114 does not
    res = run(arrays)
    clusters = pivot_levels(res.resistances)
    assert [round(x.price, 9) for x in clusters] == [110.25, 114.0]
    assert [x.touches for x in clusters] == [2, 1]
    assert pivot_levels(res.supports) == []


def test_strength_is_touches_times_recency_weight() -> None:
    """TS-IND-111: strength = sum of per-touch weights = touches * mean weight; 1.0 -> 0.3."""
    assert lv.recency_weight(0) == 1.0
    assert abs(lv.recency_weight(250) - 0.3) < 1e-12
    assert abs(lv.recency_weight(125) - 0.65) < 1e-12
    # Last bar index 99: pivots at 20, 40, 60 have ages 79, 59, 39.
    res = run(tape(100, up={20: 110.0, 40: 110.5, 60: 114.0}))
    c1, c2 = pivot_levels(res.resistances)
    assert abs(c1.strength - (weight(79) + weight(59))) < 1e-12
    assert abs(c1.strength - 2 * (weight(79) + weight(59)) / 2) < 1e-12
    assert abs(c2.strength - weight(39)) < 1e-12


def test_keep_4_strongest_above_and_4_below() -> None:
    """TS-IND-112: six resistances and six supports; the four most recent (strongest) survive."""
    up = {10: 106.0, 24: 112.0, 38: 109.0, 52: 118.0, 66: 115.0, 80: 121.0}
    down = {17: 94.0, 31: 88.0, 45: 91.0, 59: 82.0, 73: 85.0, 87: 79.0}
    arrays = tape(100, up=up, down=down)
    tol = 0.5 * atr_ref(arrays[0], arrays[1], arrays[2])
    prices = sorted([*up.values(), *down.values()])
    assert min(b - a for a, b in zip(prices, prices[1:], strict=False)) > tol  # no merging
    res = run(arrays)
    assert sorted(x.price for x in pivot_levels(res.resistances)) == [109.0, 115.0, 118.0, 121.0]
    assert sorted(x.price for x in pivot_levels(res.supports)) == [79.0, 82.0, 85.0, 91.0]


def test_52_week_high_and_low_added() -> None:
    """TS-IND-113: 52-week (252 bar) extremes are levels; older extremes are ignored."""
    up = {10: 150.0, 100: 130.0}
    down = {20: 60.0, 150: 80.0}
    res = run(tape(300, up=up, down=down))
    highs = [x for x in res.resistances if x.kind == "high52"]
    lows = [x for x in res.supports if x.kind == "low52"]
    assert [x.price for x in highs] == [130.0]  # bar 10 is outside the last 252 bars
    assert [x.price for x in lows] == [80.0]  # bar 20 is outside the last 252 bars


def prefix(arrays: tuple[Arr, Arr, Arr, Arr], n: int) -> tuple[Arr, Arr, Arr, Arr]:
    return arrays[0][:n], arrays[1][:n], arrays[2][:n], arrays[3][:n]


def test_breakout_only_on_the_bar_it_happens() -> None:
    """TS-IND-114: close 100 -> 109 through the 108 pivot on 3x volume flags once."""
    # rel volume = 3000 / ((19 * 1000 + 3000) / 20) = 3000 / 1100 = 2.73.
    high, low, close, volume = tape(80, up={30: 108.0})
    close[71:] = 109.0
    high[71:] = 110.0
    volume[71] = 3000.0
    volume[72:] = 3000.0
    arrays = (high, low, close, volume)
    before = run(prefix(arrays, 71))  # bar 70
    on_bar = run(prefix(arrays, 72))  # bar 71
    after = run(prefix(arrays, 73))  # bar 72, already above
    assert not before.breakout
    assert on_bar.breakout
    assert on_bar.broken_level is not None
    assert abs(on_bar.broken_level - 108.0) < 1e-9
    assert abs(on_bar.rel_volume - 3000.0 / 1100.0) < 1e-9
    assert not after.breakout
    assert not on_bar.breakdown


def test_breakdown_requires_support_intact_prior_day() -> None:
    """TS-IND-115: a close below support flags only if the prior close was still above it."""
    high, low, close, volume = tape(80, down={30: 92.0})
    # Intact: bar 70 close 100 (above 92), bar 71 close 91 on 3x volume.
    close[71:] = 91.0
    low[71:] = 90.0
    volume[71] = 3000.0
    flagged = run(prefix((high, low, close, volume), 72))
    assert flagged.breakdown
    assert flagged.broken_level is not None
    assert abs(flagged.broken_level - 92.0) < 1e-9
    # Not intact: bar 70 already closed at 91 (below 92); bar 71 closes lower on high volume.
    high2, low2, close2, volume2 = tape(80, down={30: 92.0})
    close2[70] = 91.0
    low2[70] = 90.0
    close2[71:] = 90.5
    low2[71:] = 89.5
    volume2[71] = 3000.0
    stale = run(prefix((high2, low2, close2, volume2), 72))
    assert not stale.breakdown


def test_nearest_support_resistance_distance_in_atr_units() -> None:
    """TS-IND-116: d_s = (close - support) / atr and d_r = (resistance - close) / atr."""
    arrays = tape(100, up={20: 110.0, 40: 110.5, 60: 114.0}, down={50: 96.0})
    atr = atr_ref(arrays[0], arrays[1], arrays[2])
    res = run(arrays)
    assert abs(res.atr - atr) < 1e-9
    assert res.nearest_support is not None
    assert res.nearest_resistance is not None
    assert res.nearest_support.price == 96.0
    assert abs(res.nearest_resistance.price - 110.25) < 1e-9
    assert res.d_s is not None
    assert res.d_r is not None
    assert abs(res.d_s - (100.0 - 96.0) / atr) < 1e-9
    assert abs(res.d_r - (110.25 - 100.0) / atr) < 1e-9


def test_insufficient_history_returns_none() -> None:
    """TS-IND-117: fewer than atr_period bars (ATR undefined) gives None."""
    assert lv.support_resistance(*tape(10)) is None
    assert lv.support_resistance(*tape(14)) is not None


def test_breakdown_flagged_only_on_the_bar_it_happens() -> None:
    """TS-IND-118: the mirror of TS-IND-114; the next bar is no longer a breakdown."""
    high, low, close, volume = tape(80, down={30: 92.0})
    close[71:] = 91.0
    low[71:] = 90.0
    volume[71:] = 3000.0
    arrays = (high, low, close, volume)
    assert not run(prefix(arrays, 71)).breakdown
    assert run(prefix(arrays, 72)).breakdown
    assert not run(prefix(arrays, 73)).breakdown


def test_breakout_requires_relative_volume_1_5() -> None:
    """TS-IND-119: rel volume 1.0 or 1.46 does not flag; 1.55 does (volume 1600 / 1030)."""
    results = []
    for v in (1000.0, 1500.0, 1600.0):
        high, low, close, volume = tape(80, up={30: 108.0})
        close[71] = 109.0
        high[71] = 110.0
        volume[71] = v
        results.append(run(prefix((high, low, close, volume), 72)))
    assert [r.breakout for r in results] == [False, False, True]
    # 1500 / ((19 * 1000 + 1500) / 20) = 1500 / 1025 = 1.4634
    assert abs(results[1].rel_volume - 1500.0 / 1025.0) < 1e-9


def test_cluster_is_anchored_not_chained() -> None:
    """TS-IND-220: pivots 0.8 apart chain, but a member more than tol from the anchor splits."""
    arrays = tape(100, up={20: 106.0, 40: 106.8, 60: 107.6})
    tol = 0.5 * atr_ref(arrays[0], arrays[1], arrays[2])
    assert 0.8 <= tol < 1.6  # 106.8 is within tol of 106.0, 107.6 is not
    clusters = pivot_levels(run(arrays).resistances)
    assert [round(x.price, 9) for x in clusters] == [106.4, 107.6]
    assert [x.touches for x in clusters] == [2, 1]


def test_unconfirmed_pivots_are_not_used() -> None:
    """TS-IND-221: a spike fewer than 5 bars before the last bar is not a confirmed pivot."""
    res = run(tape(100, up={97: 112.0, 60: 110.0}))
    assert [x.price for x in pivot_levels(res.resistances)] == [110.0]
