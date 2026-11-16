# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Ripster EMA Clouds (Signal Engine Specification, Factor 12; PRD 7.13, FR-224; ADR-058).

Matches Ripster47's TradingView indicator at its defaults: EMA on `hl2`, five clouds (8/9, 5/12,
34/50, 72/89, 180/200). EMA is the Conventions EMA (`primitives.ema`: alpha = 2 / (n + 1), seeded
with the SMA of the first n values). Direction convention: +1 bullish (short EMA above long),
-1 bearish.

Warm-up and NaN policy: a cloud is NaN until its long EMA is defined (index `long - 1`); `stack`
and `pullback` are NaN until c2 and c3 are; `bars_since_stack_flip` is also NaN while `stack` is
0. Warm-up values are never 0. Every value at bar t uses only bars at or before t.

The 8/9 pullback window is the last `lookback` bars including t (t-2 to t for the default 3; PRD
A-25), and each bar's low or high is compared with the c1 cloud of that same bar.
"""

import math
from dataclasses import dataclass

import numpy as np

from supertrends.indicators.primitives import DateArray, FloatArray, ema, resample_weekly

__all__ = [
    "RIPSTER_CLOUDS",
    "EmaCloud",
    "RipsterClouds",
    "bars_since_stack_flip",
    "cloud_stack",
    "ema_cloud",
    "ripster_clouds",
    "ripster_pullback",
    "ripster_weekly_direction",
]

RIPSTER_CLOUDS: tuple[tuple[int, int], ...] = ((8, 9), (5, 12), (34, 50), (72, 89), (180, 200))


@dataclass(frozen=True)
class EmaCloud:
    """One cloud, all arrays the length of the input.

    `top` and `bot` are the larger and smaller EMA; `direction` is +1.0 when the short EMA is
    above the long one, else -1.0; `pos` is +1.0 when close is above `top`, -1.0 below `bot`,
    0.0 inside (edges included). All NaN until both EMAs are defined.
    """

    ema_short: FloatArray
    ema_long: FloatArray
    top: FloatArray
    bot: FloatArray
    direction: FloatArray
    pos: FloatArray


@dataclass(frozen=True)
class RipsterClouds:
    """The five clouds (c1 to c5) plus `stack`, `bars_since_stack_flip` and `pullback`.

    `stack` is +1.0 when c2 lies fully above c3, -1.0 fully below, 0.0 when they overlap.
    `pullback` is +1.0 for a held bullish test of c1, -1.0 for a held bearish one, else 0.0.
    """

    clouds: tuple[EmaCloud, ...]
    stack: FloatArray
    bars_since_stack_flip: FloatArray
    pullback: FloatArray


def _check_lengths(*arrays: FloatArray) -> None:
    if len({len(a) for a in arrays}) > 1:
        msg = "input arrays must have the same length"
        raise ValueError(msg)


def _cloud_from_emas(es: FloatArray, el: FloatArray, close: FloatArray) -> EmaCloud:
    defined = ~(np.isnan(es) | np.isnan(el))
    top = np.maximum(es, el)
    bot = np.minimum(es, el)
    direction = np.where(defined, np.where(es > el, 1.0, -1.0), np.nan)
    pos = np.where(close > top, 1.0, np.where(close < bot, -1.0, 0.0))
    pos = np.where(defined, pos, np.nan)
    return EmaCloud(es, el, top, bot, direction, pos)


def ema_cloud(src: FloatArray, close: FloatArray, short: int, long: int) -> EmaCloud:
    """The cloud between EMA(src, short) and EMA(src, long), with `pos` measured on `close`."""
    _check_lengths(src, close)
    return _cloud_from_emas(ema(src, short), ema(src, long), close)


def cloud_stack(fast: EmaCloud, bias: EmaCloud) -> FloatArray:
    """+1 where `fast` (c2) lies fully above `bias` (c3), -1 fully below, 0 overlapping."""
    out = np.where(fast.bot > bias.top, 1.0, np.where(fast.top < bias.bot, -1.0, 0.0))
    undefined = np.isnan(fast.top) | np.isnan(bias.top)
    return np.where(undefined, np.nan, out)


def bars_since_stack_flip(stack: FloatArray) -> FloatArray:
    """Bars since `stack` last changed to its current nonzero value: 0 on the change bar.

    The first defined bar counts as a change. NaN where `stack` is NaN or 0.
    """
    out = np.full(len(stack), np.nan)
    since = 0.0
    prev = math.nan
    for t, s in enumerate(stack):
        if math.isnan(s):
            continue
        since = since + 1.0 if s == prev else 0.0
        prev = float(s)
        if s != 0:
            out[t] = since
    return out


def ripster_pullback(  # noqa: PLR0913, PLR0917
    high: FloatArray,
    low: FloatArray,
    close: FloatArray,
    c1: EmaCloud,
    stack: FloatArray,
    lookback: int = 3,
) -> FloatArray:
    """The 8/9 pullback test (FR-333): +1 held bullish, -1 held bearish, 0 otherwise.

    Bullish (stack +1): some low <= top(c1) within the last `lookback` bars and close > bot(c1).
    Bearish (stack -1): some high >= bot(c1) within the window and close < top(c1). NaN where
    `stack` or c1 is undefined. `lookback` is `ripster.pullback_lookback_bars`.
    """
    if lookback < 1:
        msg = f"lookback must be at least 1, got {lookback}"
        raise ValueError(msg)
    _check_lengths(high, low, close, c1.top, stack)
    with np.errstate(invalid="ignore"):
        tested_up = (low <= c1.top).astype(np.float64)
        tested_down = (high >= c1.bot).astype(np.float64)
    out = np.full(len(close), np.nan)
    for t in range(len(close)):
        s = stack[t]
        if math.isnan(s) or math.isnan(c1.top[t]):
            continue
        lo = max(0, t - lookback + 1)
        if s == 1 and tested_up[lo : t + 1].any() and close[t] > c1.bot[t]:
            out[t] = 1.0
        elif s == -1 and tested_down[lo : t + 1].any() and close[t] < c1.top[t]:
            out[t] = -1.0
        else:
            out[t] = 0.0
    return out


def ripster_clouds(
    high: FloatArray,
    low: FloatArray,
    close: FloatArray,
    clouds: tuple[tuple[int, int], ...] = RIPSTER_CLOUDS,
    pullback_lookback: int = 3,
) -> RipsterClouds:
    """All five clouds on hl2 plus stack, bars since the stack flip, and the pullback test.

    `clouds` and `pullback_lookback` are the `config/scoring.yaml` `ripster` values, passed
    explicitly by the caller; the defaults are the specification's.
    """
    if len(clouds) != len(RIPSTER_CLOUDS):
        msg = f"expected five (short, long) cloud pairs, got {len(clouds)}"
        raise ValueError(msg)
    _check_lengths(high, low, close)
    src = (high + low) / 2.0
    built = tuple(ema_cloud(src, close, short, long) for short, long in clouds)
    stack = cloud_stack(built[1], built[2])
    return RipsterClouds(
        clouds=built,
        stack=stack,
        bars_since_stack_flip=bars_since_stack_flip(stack),
        pullback=ripster_pullback(high, low, close, built[0], stack, pullback_lookback),
    )


class _WeeklyEma:
    """EMA over completed weekly values, with a one-step peek for the partial week."""

    def __init__(self, n: int) -> None:
        if n < 1:
            msg = f"window n must be at least 1, got {n}"
            raise ValueError(msg)
        self.n = n
        self.alpha = 2.0 / (n + 1)
        self.seen: list[float] = []  # the first n - 1 completed values, for the seed
        self.value = math.nan

    def commit(self, x: float) -> None:
        if len(self.seen) < self.n - 1:
            self.seen.append(x)
        elif math.isnan(self.value):
            self.value = float(np.mean([*self.seen, x]))
        else:
            self.value += self.alpha * (x - self.value)

    def peek(self, x: float) -> float:
        if len(self.seen) < self.n - 1:
            return math.nan
        if math.isnan(self.value):
            return float(np.mean([*self.seen, x]))
        return self.value + self.alpha * (x - self.value)


def ripster_weekly_direction(  # noqa: PLR0913, PLR0917
    dates: DateArray,
    open_: FloatArray,
    high: FloatArray,
    low: FloatArray,
    close: FloatArray,
    volume: FloatArray,
    short: int = 34,
    long: int = 50,
) -> FloatArray:
    """`rc_dir_w`: the 34/50 cloud direction on weekly bars, as known at each daily bar.

    Daily bars are resampled to weekly bars (`resample_weekly`, ADR-033) and the cloud runs on
    weekly hl2. The value at daily bar t treats the current week as a partial weekly bar holding
    the week's bars up to t, so it uses only bars at or before t (as `supertrend_weekly_direction`
    does). O(n). NaN until `long` weekly bars exist. Evidence only; not scored.
    """
    weekly = resample_weekly(dates, open_, high, low, close, volume)
    out = np.full(len(close), np.nan)
    es, el = _WeeklyEma(short), _WeeklyEma(long)
    week = 0
    week_high, week_low = -np.inf, np.inf
    for t in range(len(close)):
        w = int(weekly.week_index[t])
        if w != week:  # the previous week is complete: commit it
            hl2 = (float(weekly.high[week]) + float(weekly.low[week])) / 2.0
            es.commit(hl2)
            el.commit(hl2)
            week, week_high, week_low = w, -np.inf, np.inf
        week_high = max(week_high, float(high[t]))
        week_low = min(week_low, float(low[t]))
        x = (week_high + week_low) / 2.0
        s, lg = es.peek(x), el.peek(x)
        if not (math.isnan(s) or math.isnan(lg)):
            out[t] = 1.0 if s > lg else -1.0
    return out
