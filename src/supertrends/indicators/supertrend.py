# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Supertrend (Signal Engine Specification, Factor 1; PRD FR-2xx; ARCHITECTURE section 2).

Matches TradingView's built-in Supertrend (ATR length 10, factor 3.0 by default). The recursion
is implemented once, as a one-bar `_advance` step, and used both for the full series and for the
per-day weekly direction. Direction convention: +1 up, -1 down. TradingView's opposite sign is
converted only inside the parity test, never here.

Warm-up and NaN policy: ATR (Wilder RMA of true range, seeded with the mean of the first
`atr_length` true ranges) is defined from index `atr_length - 1`. Every output is NaN before that
index. On that first defined bar `atr[t-1]` is undefined, so the direction is -1 (down) and the
line is `final_upper`, as in TradingView. A NaN in high, low or close poisons the ATR and so every
output from that bar on (the same policy as `rma`). The line is final_lower when up and
final_upper when down; the value at bar t uses only bars at or before t (no look-ahead).
"""

import math
from dataclasses import dataclass

import numpy as np

from supertrends.indicators.primitives import DateArray, FloatArray, resample_weekly

__all__ = [
    "SupertrendResult",
    "bars_since_flip",
    "distance_atr",
    "supertrend_weekly_direction",
]
# `supertrend` (the function) is deliberately not in `__all__`: the package aggregator star-imports
# every module's `__all__`, and a function named like its module would replace the submodule
# attribute `supertrends.indicators.supertrend` and break the aggregation. Import it as
# `from supertrends.indicators.supertrend import supertrend`.

_NAN = float("nan")


@dataclass(frozen=True)
class SupertrendResult:
    """Supertrend output arrays, all the length of the input.

    `line` is the Supertrend (also the invalidation level, `st_line`); `direction` is +1.0 up or
    -1.0 down; `final_upper` and `final_lower` are the ratcheted bands; `atr` is the Wilder ATR.
    All are NaN while the ATR is undefined.
    """

    line: FloatArray
    direction: FloatArray
    final_upper: FloatArray
    final_lower: FloatArray
    atr: FloatArray


@dataclass(frozen=True, slots=True)
class _State:
    """Recursion state after one bar."""

    count: int = 0  # bars seen
    prev_close: float = _NAN
    tr_sum: float = 0.0  # sum of true ranges while seeding
    atr: float = _NAN
    final_upper: float = _NAN
    final_lower: float = _NAN
    line: float = _NAN
    direction: float = _NAN


def _advance(  # noqa: PLR0913, PLR0917
    s: _State, high: float, low: float, close: float, atr_length: int, factor: float
) -> _State:
    """Process one bar: true range, Wilder ATR, band ratcheting, direction, line."""
    tr = (
        high - low
        if s.count == 0
        else max(high - low, abs(high - s.prev_close), abs(low - s.prev_close))
    )
    count = s.count + 1
    if count < atr_length:
        return _State(count, close, s.tr_sum + tr)
    if count == atr_length:
        atr = (s.tr_sum + tr) / atr_length
    else:
        atr = (s.atr * (atr_length - 1) + tr) / atr_length
    if math.isnan(atr):  # NaN input poisoned the ATR
        return _State(count, close, s.tr_sum, _NAN)
    hl2 = (high + low) / 2.0
    basic_up = hl2 + factor * atr
    basic_lo = hl2 - factor * atr
    if math.isnan(
        s.atr
    ):  # first defined bar: no previous bands (TradingView uses nz(), same result)
        final_up, final_lo, direction = basic_up, basic_lo, -1.0
    else:
        final_up = (
            basic_up if basic_up < s.final_upper or s.prev_close > s.final_upper else s.final_upper
        )
        final_lo = (
            basic_lo if basic_lo > s.final_lower or s.prev_close < s.final_lower else s.final_lower
        )
        if s.line == s.final_upper:
            direction = 1.0 if close > final_up else -1.0
        else:
            direction = -1.0 if close < final_lo else 1.0
    line = final_lo if direction == 1.0 else final_up
    return _State(count, close, s.tr_sum, atr, final_up, final_lo, line, direction)


def supertrend(
    high: FloatArray,
    low: FloatArray,
    close: FloatArray,
    atr_length: int = 10,
    factor: float = 3.0,
) -> SupertrendResult:
    """Supertrend with TradingView semantics (BUILD_PROMPT Factor 1).

    Parameters: 1-D float64 arrays of equal length; `atr_length` (default 10) and `factor`
    (default 3.0) are the `config/scoring.yaml` defaults, passed explicitly by the caller.
    Warm-up: NaN before index `atr_length - 1`; that bar is direction -1. No lag beyond the ATR
    window; a flip appears on the bar whose close crosses the opposite band.
    """
    if atr_length < 1:
        msg = f"atr_length must be at least 1, got {atr_length}"
        raise ValueError(msg)
    if not len(high) == len(low) == len(close):
        msg = "high, low and close must have the same length"
        raise ValueError(msg)
    n = len(close)
    out = np.full((5, n), np.nan)
    state = _State()
    for t in range(n):
        state = _advance(state, float(high[t]), float(low[t]), float(close[t]), atr_length, factor)
        out[:, t] = (state.line, state.direction, state.final_upper, state.final_lower, state.atr)
    return SupertrendResult(
        line=out[0], direction=out[1], final_upper=out[2], final_lower=out[3], atr=out[4]
    )


def bars_since_flip(direction: FloatArray) -> FloatArray:
    """Bars since the direction last changed: 0 on the flip bar, 1 on the next, and so on.

    The first defined bar counts as 0 (the run starts there). NaN where `direction` is NaN.
    """
    out = np.full(len(direction), np.nan)
    since = 0.0
    prev = _NAN
    for t, d in enumerate(direction):
        if math.isnan(d):
            continue
        since = since + 1.0 if d == prev else 0.0
        prev = float(d)
        out[t] = since
    return out


def distance_atr(close: FloatArray, line: FloatArray, atr: FloatArray) -> FloatArray:
    """Signed distance of close from the line in ATR units: `(close - line) / atr`.

    Positive above the line (uptrend side). NaN where the line or ATR is NaN or the ATR is zero.
    """
    safe = np.where(atr > 0, atr, np.nan)
    return np.asarray((close - line) / safe, dtype=np.float64)


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
    """Weekly Supertrend direction (`st_dir_w`) as known at the close of each daily bar.

    The daily bars are resampled to weekly bars (`resample_weekly`, ADR-033) and Supertrend runs
    on them. The value at daily bar t is the weekly direction after a weekly bar that holds the
    week's bars up to and including t, so it uses only bars at or before t (the current week is
    partial: its high, low and close so far). The value for a day of a finished week therefore
    equals what the same call returns on data truncated at that day; it can differ from the final
    weekly direction of that week, and that is intended. Cost is O(n): the state is advanced once
    per completed week and one extra step per day. NaN until `atr_length` weekly bars exist.
    """
    weekly = resample_weekly(dates, open_, high, low, close, volume)
    out = np.full(len(close), np.nan)
    if len(close) == 0:
        return out
    state = _State()  # after the last completed week
    week = 0
    week_high, week_low = -np.inf, np.inf
    for t in range(len(close)):
        w = int(weekly.week_index[t])
        if w != week:  # the previous week is complete: commit it
            state = _advance(
                state,
                float(weekly.high[week]),
                float(weekly.low[week]),
                float(weekly.close[week]),
                atr_length,
                factor,
            )
            week, week_high, week_low = w, -np.inf, np.inf
        week_high = max(week_high, float(high[t]))
        week_low = min(week_low, float(low[t]))
        out[t] = _advance(state, week_high, week_low, float(close[t]), atr_length, factor).direction
    return out
