# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Ranking, pick counts, nearest miss and the daily selection (BUILD_PROMPT "Selection rules";
FR-404 to FR-412; ADR-050; S3-T06).

Buys rank by display descending and sells by display ascending. Ties break in order: higher
confidence, more recent Supertrend flip (smaller `bars_since_flip`), higher relative volume,
alphabetical ticker. Each side publishes at most `selection.max_buys` / `selection.max_sells`
picks after the correlation guard and is never padded. Pure: no I/O, clock or randomness.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from supertrends.scoring.composite import Band
from supertrends.scoring.config import ScoringConfig
from supertrends.selection.candidates import (
    CandidateCheck,
    Exclusion,
    SelectionInput,
    Side,
)

__all__ = [
    "AlsoQualified",
    "NearestMiss",
    "Pick",
    "PriorPicks",
    "Selection",
    "days_on_list",
    "nearest_miss",
    "rank_candidates",
    "rank_key",
    "select",
]

RankKey = tuple[float, float, float, float, str]


@dataclass(frozen=True)
class Pick:
    """A published pick. `rank` starts at 1 on each side."""

    rank: int
    side: Side
    ticker: str
    display_score: float
    confidence: float
    band: Band
    days_on_list: int
    entry: SelectionInput


@dataclass(frozen=True)
class AlsoQualified:
    """A candidate the correlation guard skipped, with the pick it duplicates (FR-410)."""

    ticker: str
    side: Side
    display_score: float
    confidence: float
    duplicates: str
    correlation: float
    entry: SelectionInput


@dataclass(frozen=True)
class NearestMiss:
    """The scored ticker closest to a side that did not qualify, and why (FR-408)."""

    ticker: str
    side: Side
    display_score: float
    threshold: float
    reason: str


@dataclass(frozen=True)
class PriorPicks:
    """The tickers published on each side on one earlier trading day (for `days_on_list`)."""

    buys: frozenset[str]
    sells: frozenset[str]


@dataclass(frozen=True)
class Selection:
    """The result of one day's selection.

    * `buys`, `sells`: picks in rank order, never more than the configured maximum.
    * `also_qualified`: guard-skipped candidates, buys first, each side in rank order.
    * `nearest_miss`: per side, present (not None) only when the side has fewer picks than its
      maximum and some scored ticker missed.
    * `excluded`: tickers excluded before scoring, sorted by ticker.
    * `checks`: both sides' verdicts for every scored ticker, sorted by ticker.
    """

    buys: tuple[Pick, ...]
    sells: tuple[Pick, ...]
    also_qualified: tuple[AlsoQualified, ...]
    nearest_miss: Mapping[Side, NearestMiss | None]
    excluded: tuple[Exclusion, ...]
    checks: tuple[CandidateCheck, ...]


def rank_key(entry: SelectionInput, side: Side) -> RankKey:
    """Sort key: smaller ranks first. Applies the full tie-breaker chain."""
    raise NotImplementedError


def rank_candidates(entries: Sequence[SelectionInput], side: Side) -> tuple[SelectionInput, ...]:
    """`entries` in rank order for `side`."""
    raise NotImplementedError


def days_on_list(ticker: str, side: Side, previous: Sequence[PriorPicks]) -> int:
    """Consecutive published days on `side`, counting today; `previous` is most recent first."""
    raise NotImplementedError


def nearest_miss(
    entries: Sequence[SelectionInput], side: Side, config: ScoringConfig
) -> NearestMiss | None:
    """The non-qualifying, non-stale ticker nearest to `side`'s threshold (ADR-050, ADR-065)."""
    raise NotImplementedError


def select(
    entries: Sequence[SelectionInput],
    closes: Mapping[str, Mapping[date, float]],
    config: ScoringConfig,
    *,
    excluded: Sequence[Exclusion] = (),
    previous: Sequence[PriorPicks] = (),
) -> Selection:
    """Run the full daily selection over the scored tickers."""
    raise NotImplementedError
