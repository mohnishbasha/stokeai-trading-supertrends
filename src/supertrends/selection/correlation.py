# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Correlation guard (BUILD_PROMPT "Selection rules"; FR-409, FR-410; S3-T06).

Walk a side's ranked candidates in order and skip any candidate whose 60-day return correlation
(`selection.correlation_window`) with an already selected pick on that side is above 0.9
(`selection.correlation_max`), until the side is full or candidates run out. Correlation is the
Pearson correlation of daily close-to-close simple returns over the last `window` sessions both
tickers have. Pure: no I/O, clock or randomness.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from itertools import pairwise

__all__ = [
    "CorrelationFn",
    "Duplicate",
    "GuardResult",
    "correlation_guard",
    "pearson",
    "return_correlation",
    "simple_returns",
]

CorrelationFn = Callable[[str, str], float | None]


@dataclass(frozen=True)
class Duplicate:
    """A candidate skipped by the guard, the pick it duplicates and their correlation."""

    ticker: str
    duplicates: str
    correlation: float


@dataclass(frozen=True)
class GuardResult:
    """Picked tickers in rank order and the skipped duplicates in walk order."""

    picked: tuple[str, ...]
    skipped: tuple[Duplicate, ...]


def simple_returns(closes: Sequence[float]) -> list[float]:
    """Close-to-close simple returns `close[i] / close[i-1] - 1`.

    Raises ValueError for a close that is not a finite positive number.
    """
    for close in closes:
        if not math.isfinite(close) or close <= 0:
            msg = f"close must be a finite positive number, got {close!r}"
            raise ValueError(msg)
    return [b / a - 1.0 for a, b in pairwise(closes)]


def pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Pearson correlation of two equal-length series, clipped to -1..1.

    None when undefined: fewer than 2 points or a series with zero variance. Raises ValueError
    when the lengths differ.
    """
    if len(x) != len(y):
        msg = f"series length differs: {len(x)} and {len(y)}"
        raise ValueError(msg)
    n = len(x)
    if n < 2:
        return None
    mx = math.fsum(x) / n
    my = math.fsum(y) / n
    dx = [v - mx for v in x]
    dy = [v - my for v in y]
    sxx = math.fsum(v * v for v in dx)
    syy = math.fsum(v * v for v in dy)
    if sxx == 0.0 or syy == 0.0:
        return None
    sxy = math.fsum(a * b for a, b in zip(dx, dy, strict=True))
    return max(-1.0, min(1.0, sxy / math.sqrt(sxx * syy)))


def return_correlation(
    a: Mapping[date, float], b: Mapping[date, float], window: int
) -> float | None:
    """Correlation of the last `window` daily returns over the dates both series share.

    Uses the last `window + 1` shared dates (so `window` returns, each spanning the same two
    dates for both tickers). None when fewer dates are shared or a series is flat (PRD A-33).
    Raises ValueError for a window below 2 or a bad close.
    """
    if window < 2:
        msg = f"window must be >= 2, got {window}"
        raise ValueError(msg)
    shared = sorted(a.keys() & b.keys())
    if len(shared) < window + 1:
        return None
    dates = shared[-(window + 1) :]
    return pearson(simple_returns([a[d] for d in dates]), simple_returns([b[d] for d in dates]))


def correlation_guard(
    ranked: Sequence[str],
    correlation: CorrelationFn,
    *,
    max_picks: int,
    max_correlation: float,
) -> GuardResult:
    """Walk `ranked` in order, picking up to `max_picks` and skipping duplicates.

    A candidate is skipped when its correlation with any pick so far is above `max_correlation`
    (equal is kept; undefined is kept). The skipped entry names the pick it correlates with most,
    the higher-ranked pick on a tie. The walk stops when the side is full, so later candidates are
    neither picked nor listed (ADR-065).
    """
    picked: list[str] = []
    skipped: list[Duplicate] = []
    for ticker in ranked:
        if len(picked) >= max_picks:
            break
        worst: Duplicate | None = None
        for pick in picked:
            corr = correlation(pick, ticker)
            if (
                corr is not None
                and corr > max_correlation
                and (worst is None or corr > worst.correlation)
            ):
                worst = Duplicate(ticker=ticker, duplicates=pick, correlation=corr)
        if worst is None:
            picked.append(ticker)
        else:
            skipped.append(worst)
    return GuardResult(picked=tuple(picked), skipped=tuple(skipped))
