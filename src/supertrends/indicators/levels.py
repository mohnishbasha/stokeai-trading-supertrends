# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Support and resistance level clustering (owned by S2-T06; Factor 7).

Spec: BUILD_PROMPT "Factor 7: Support and resistance". Confirmed width-5 pivot highs and lows
over the last `lookback` (250) bars are clustered; a cluster is a level whose strength is
`touches * recency_weight`. The 4 strongest levels above price (resistance) and 4 below
(support) are kept, and the 52-week (252 bar) high and low are added as extra levels.

Clustering (ADR-054, PRD section 17): pivot prices are sorted ascending and a cluster is
anchored on its lowest price; a pivot joins the open cluster while `price - anchor <= 0.5 * ATR`,
otherwise it opens a new cluster. Every member is therefore within 0.5 ATR of every other
member, with no chaining. The level price is the mean of the member prices.

Strength: each touch (pivot) weighs `recency_weight(age)`, decaying linearly from 1.0 (age 0) to
0.3 (age `lookback`); a cluster's strength is the sum of its touch weights, which equals
`touches * mean(weight)`.

`support_resistance` is an as-of-last-bar function: to evaluate bar t, pass `bars[:t+1]`.
Pivots are only used once confirmed (5 bars after the pivot bar), so nothing looks ahead.
Breakout and breakdown are evaluated against the levels as they stood at the previous bar
("intact yesterday"), so a flag appears only on the bar the close crosses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from supertrends.indicators.primitives import Pivot, atr, pivots, sma

FloatArray = NDArray[np.float64]

__all__ = ["Level", "SupportResistance", "recency_weight", "support_resistance"]


@dataclass(frozen=True)
class Level:
    """A support or resistance level. `touches` is 1 for the 52-week extremes."""

    price: float
    strength: float
    touches: int
    kind: Literal["cluster", "high52", "low52"]


@dataclass(frozen=True)
class SupportResistance:
    """Levels as of the last bar.

    `supports` (price <= close) are nearest first; `resistances` (price > close) nearest first.
    `d_s` and `d_r` are ATR-unit distances to the nearest level, None when that side is empty
    (no resistance happens when the close sits at the 52-week high). `breakout` and `breakdown`
    are true only on the bar of the cross; `broken_level` is the price of the level crossed
    (the highest for a breakout, the lowest for a breakdown).
    """

    close: float
    atr: float
    supports: tuple[Level, ...]
    resistances: tuple[Level, ...]
    nearest_support: Level | None
    nearest_resistance: Level | None
    d_s: float | None
    d_r: float | None
    rel_volume: float
    breakout: bool
    breakdown: bool
    broken_level: float | None


def recency_weight(age: int, lookback: int = 250, min_weight: float = 0.3) -> float:
    """Linear decay from 1.0 at age 0 to `min_weight` at age `lookback` (bars before today)."""
    return 1.0 - (1.0 - min_weight) * age / lookback


def _cluster(
    pivs: list[Pivot], tol: float, last: int, lookback: int, min_weight: float
) -> list[Level]:
    out: list[Level] = []
    members: list[Pivot] = []

    def flush() -> None:
        if members:
            strength = sum(recency_weight(last - m.index, lookback, min_weight) for m in members)
            price = sum(m.price for m in members) / len(members)
            out.append(Level(price, strength, len(members), "cluster"))

    for pv in sorted(pivs, key=lambda x: (x.price, x.index)):
        if members and pv.price - members[0].price > tol:
            flush()
            members = []
        members.append(pv)
    flush()
    return out


def _levels_at(  # noqa: PLR0913, PLR0917
    all_pivots: list[Pivot],
    high: FloatArray,
    low: FloatArray,
    close: float,
    atr_now: float,
    end: int,
    lookback: int,
    cluster_atr: float,
    min_weight: float,
    year_bars: int,
    per_side: int,
) -> tuple[list[Level], list[Level]]:
    """(supports, resistances) using bars [0, end); both nearest first."""
    last = end - 1
    usable = [pv for pv in all_pivots if pv.confirmed_at <= last and pv.index > last - lookback]
    levels = _cluster(usable, cluster_atr * atr_now, last, lookback, min_weight)
    supports = [x for x in levels if x.price <= close]
    resistances = [x for x in levels if x.price > close]

    def strongest(side: list[Level]) -> list[Level]:
        ranked = sorted(side, key=lambda x: (-x.strength, abs(x.price - close), x.price))
        return ranked[:per_side]

    supports = strongest(supports)
    resistances = strongest(resistances)
    start = max(0, end - year_bars)
    hi_win = high[start:end]
    lo_win = low[start:end]
    hi_i = start + int(len(hi_win) - 1 - np.argmax(hi_win[::-1]))
    lo_i = start + int(len(lo_win) - 1 - np.argmin(lo_win[::-1]))
    high52 = Level(
        float(high[hi_i]), recency_weight(last - hi_i, lookback, min_weight), 1, "high52"
    )
    low52 = Level(float(low[lo_i]), recency_weight(last - lo_i, lookback, min_weight), 1, "low52")
    for extra in (high52, low52):
        (supports if extra.price <= close else resistances).append(extra)
    supports.sort(key=lambda x: (-x.price, -x.strength))
    resistances.sort(key=lambda x: (x.price, -x.strength))
    return supports, resistances


def support_resistance(  # noqa: PLR0913
    high: FloatArray,
    low: FloatArray,
    close: FloatArray,
    volume: FloatArray,
    *,
    width: int = 5,
    lookback: int = 250,
    atr_period: int = 14,
    cluster_atr: float = 0.5,
    min_weight: float = 0.3,
    year_bars: int = 252,
    rv_period: int = 20,
    rv_min: float = 1.5,
    per_side: int = 4,
) -> SupportResistance | None:
    """Support and resistance as of the last bar; None while ATR is in warm-up.

    Relative volume is `volume / SMA(volume, rv_period)` at the last bar (NaN until
    `rv_period` bars exist, which suppresses the breakout flags). Needs at least `atr_period`
    bars. A pivot at bar p is used from bar p + width on, and only the last `lookback` bars'
    pivots count.
    """
    n = len(close)
    atr_arr = atr(high, low, close, atr_period)
    if n == 0 or np.isnan(atr_arr[-1]):
        return None
    atr_now = float(atr_arr[-1])
    px = float(close[-1])
    all_pivots = pivots(high, low, width)

    def build(end: int, atr_at: float, px_at: float) -> tuple[list[Level], list[Level]]:
        return _levels_at(
            all_pivots, high, low, px_at, atr_at, end, lookback, cluster_atr, min_weight,
            year_bars, per_side,
        )  # fmt: skip

    supports, resistances = build(n, atr_now, px)
    rel = float(volume[-1] / sma(volume, rv_period)[-1]) if n >= rv_period else float("nan")
    breakout = breakdown = False
    broken: float | None = None
    if n >= 2 and rel >= rv_min and not np.isnan(atr_arr[-2]):
        prev_close = float(close[-2])
        prev_sup, prev_res = build(n - 1, float(atr_arr[-2]), prev_close)
        crossed_up = [x.price for x in prev_res if px > x.price]
        crossed_dn = [x.price for x in prev_sup if px < x.price]
        if crossed_up:
            breakout, broken = True, max(crossed_up)
        if crossed_dn:
            breakdown, broken = True, min(crossed_dn)
    nearest_s = supports[0] if supports else None
    nearest_r = resistances[0] if resistances else None
    return SupportResistance(
        close=px,
        atr=atr_now,
        supports=tuple(supports),
        resistances=tuple(resistances),
        nearest_support=nearest_s,
        nearest_resistance=nearest_r,
        d_s=(px - nearest_s.price) / atr_now if nearest_s else None,
        d_r=(nearest_r.price - px) / atr_now if nearest_r else None,
        rel_volume=rel,
        breakout=breakout,
        breakdown=breakdown,
        broken_level=broken,
    )
