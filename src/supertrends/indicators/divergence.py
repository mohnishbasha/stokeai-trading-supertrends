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

import numpy as np

from supertrends.indicators.primitives import ema, obv, pivot_masks, rsi

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


def _check(high: FloatArray, low: FloatArray, osc: FloatArray, width: int) -> None:
    if not (len(high) == len(low) == len(osc)):
        msg = "high, low, and osc must have the same length"
        raise ValueError(msg)
    if width < 1:
        msg = f"pivot width must be >= 1, got {width}"
        raise ValueError(msg)


def _classify(price1: float, price2: float, osc1: float, osc2: float, side: Side) -> Kind | None:
    if np.isnan(osc1) or np.isnan(osc2) or price1 == price2 or osc1 == osc2:
        return None
    price_up = price2 > price1
    osc_up = osc2 > osc1
    if price_up == osc_up:
        return None
    # Opposite directions. Bullish: price lower low + osc higher low is regular.
    # Bearish: price higher high + osc lower high is regular.
    if side == "bullish":
        return "regular" if not price_up else "hidden"
    return "regular" if price_up else "hidden"


def _candidates(  # noqa: PLR0913, PLR0917
    high: FloatArray,
    low: FloatArray,
    osc: FloatArray,
    oscillator: str,
    timeframe: Timeframe,
    width: int,
    lookback: int,
    recency: int,
) -> list[tuple[Divergence, int]]:
    """Every divergence with the last bar at which it is still the active comparison."""
    _check(high, low, osc, width)
    hi_mask, lo_mask = pivot_masks(high, low, width)
    sides: tuple[tuple[Side, BoolArray, FloatArray], ...] = (
        ("bullish", lo_mask, low),
        ("bearish", hi_mask, high),
    )
    out: list[tuple[Divergence, int]] = []
    for side, mask, prices in sides:
        idx = np.flatnonzero(mask)
        for j in range(1, len(idx)):
            p1, p2 = int(idx[j - 1]), int(idx[j])
            kind = _classify(
                float(prices[p1]), float(prices[p2]), float(osc[p1]), float(osc[p2]), side
            )
            if kind is None:
                continue
            first = p2 + width
            last = min(p2 + recency, p1 + lookback - 1)
            if j + 1 < len(idx):
                # A newer confirmed pivot replaces p2 as the "most recent" one.
                last = min(last, int(idx[j + 1]) + width - 1)
            if last < first:
                continue
            record = Divergence(
                kind,
                side,
                oscillator,
                timeframe,
                p1,
                p2,
                float(prices[p1]),
                float(prices[p2]),
                float(osc[p1]),
                float(osc[p2]),
                first,
            )
            out.append((record, last))
    out.sort(key=lambda c: (c[0].confirmed_at, c[0].side, c[0].p2))
    return out


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
    """Every divergence that was active at some bar, sorted by `confirmed_at`.

    The record is usable from bar `confirmed_at` on; a harness truncating the input at t gets
    exactly the records with `confirmed_at <= t`.
    """
    cands = _candidates(high, low, osc, oscillator, timeframe, width, lookback, recency)
    return [rec for rec, _ in cands]


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
    """Divergences active as of bar `as_of` (default the last bar), for one oscillator.

    Parameters default to the daily Factor 4 rules; use `width=3` for weekly bars. Lag is
    `width` bars. Returns at most one pivot-low and one pivot-high comparison.
    """
    n = len(high)
    t = n - 1 if as_of is None else as_of
    if n == 0 or not 0 <= t < n:
        return []
    cands = _candidates(high, low, osc, oscillator, timeframe, width, lookback, recency)
    return [rec for rec, last in cands if rec.confirmed_at <= t <= last]


def divergence_series(  # noqa: PLR0913
    high: FloatArray,
    low: FloatArray,
    osc: FloatArray,
    *,
    width: int = DAILY_WIDTH,
    lookback: int = LOOKBACK,
    recency: int = RECENCY,
) -> DivergenceSeries:
    """Per-bar flags: value at t equals `detect_divergences(..., as_of=t)` on the four types.

    Intended for the no-look-ahead harness: the flag at t uses only bars <= t.
    """
    n = len(high)
    flags = {
        (k, s): np.zeros(n, dtype=np.bool_)
        for k in ("regular", "hidden")
        for s in ("bullish", "bearish")
    }
    for rec, last in _candidates(high, low, osc, "", "daily", width, lookback, recency):
        flags[(rec.kind, rec.side)][rec.confirmed_at : min(last, n - 1) + 1] = True
    return DivergenceSeries(
        flags[("regular", "bullish")],
        flags[("regular", "bearish")],
        flags[("hidden", "bullish")],
        flags[("hidden", "bearish")],
    )


def _macd_hist(close: FloatArray) -> FloatArray:
    """MACD histogram (12, 26, 9), NaN during warm-up.

    Mirrors `momentum.macd` (S2-T03); kept local so this module does not depend on it. The S2-T08
    harness cross-checks the two.
    """
    line = ema(close, 12) - ema(close, 26)
    out = np.full(len(close), np.nan)
    valid = np.flatnonzero(~np.isnan(line))
    if len(valid) == 0:
        return out
    start = int(valid[0])
    out[start:] = line[start:] - ema(line[start:], 9)
    return out


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
    """RSI(14), MACD histogram(12, 26, 9), and OBV divergences, each reported separately.

    Oscillators are computed from `close` (and `volume` for OBV) with the primitives; the
    oscillator name on each record is `rsi`, `macd_hist`, or `obv`.
    """
    oscillators = {"rsi": rsi(close, 14), "macd_hist": _macd_hist(close), "obv": obv(close, volume)}
    found: list[Divergence] = []
    for name, values in oscillators.items():
        found += detect_divergences(
            high,
            low,
            values,
            oscillator=name,
            timeframe=timeframe,
            width=width,
            lookback=lookback,
            recency=recency,
            as_of=as_of,
        )
    return found


def detect_weekly_divergences(
    weekly: WeeklyBars,
    *,
    lookback: int = LOOKBACK,
    recency: int = RECENCY,
    as_of: int | None = None,
) -> list[Divergence]:
    """All three oscillators on `resample_weekly` bars with pivot width 3 (indexes are weeks).

    The last weekly bar may be a partial week; a pivot it helps confirm can be revised when the
    week completes, so callers needing strict stability should pass only completed weeks.
    """
    return detect_all_divergences(
        weekly.high,
        weekly.low,
        weekly.close,
        weekly.volume,
        timeframe="weekly",
        width=WEEKLY_WIDTH,
        lookback=lookback,
        recency=recency,
        as_of=as_of,
    )
