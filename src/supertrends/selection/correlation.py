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

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

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
    """Close-to-close simple returns `close[i] / close[i-1] - 1`."""
    raise NotImplementedError


def pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Pearson correlation of two equal-length series; None when undefined."""
    raise NotImplementedError


def return_correlation(
    a: Mapping[date, float], b: Mapping[date, float], window: int
) -> float | None:
    """Correlation of the last `window` daily returns over the dates both series share."""
    raise NotImplementedError


def correlation_guard(
    ranked: Sequence[str],
    correlation: CorrelationFn,
    *,
    max_picks: int,
    max_correlation: float,
) -> GuardResult:
    """Walk `ranked` in order, picking up to `max_picks` and skipping duplicates."""
    raise NotImplementedError
