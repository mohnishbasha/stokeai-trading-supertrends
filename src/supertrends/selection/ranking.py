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

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from supertrends.scoring.composite import Band
from supertrends.scoring.config import ScoringConfig
from supertrends.selection.candidates import (
    SIDES,
    STALE,
    CandidateCheck,
    Exclusion,
    SelectionInput,
    Side,
    buy_threshold,
    check_side,
    evaluate_candidate,
    sell_threshold,
)
from supertrends.selection.correlation import correlation_guard, return_correlation

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
    """Sort key: smaller ranks first. Applies the full tie-breaker chain.

    Display (descending for buys, ascending for sells), then higher confidence, then smaller
    `bars_since_flip`, then higher relative volume, then ticker A to Z. An unknown flip age or
    relative volume ranks after any known value.
    """
    side = check_side(side)
    display = -entry.display_score if side == "buy" else entry.display_score
    flip = math.inf if entry.bars_since_flip is None else float(entry.bars_since_flip)
    rel_volume = math.inf if entry.relative_volume is None else -entry.relative_volume
    return (display, -entry.confidence, flip, rel_volume, entry.ticker)


def rank_candidates(entries: Sequence[SelectionInput], side: Side) -> tuple[SelectionInput, ...]:
    """`entries` in rank order for `side` (the input order never matters)."""
    side = check_side(side)
    return tuple(sorted(entries, key=lambda e: rank_key(e, side)))


def days_on_list(ticker: str, side: Side, previous: Sequence[PriorPicks]) -> int:
    """Consecutive published days on `side`, counting today; `previous` is most recent first.

    FR-411: ORCL a buy on the previous two published days and today gives 3. A day without it
    on that side ends the streak.
    """
    side = check_side(side)
    days = 1
    for prior in previous:
        if ticker not in (prior.buys if side == "buy" else prior.sells):
            break
        days += 1
    return days


def nearest_miss(
    entries: Sequence[SelectionInput], side: Side, config: ScoringConfig
) -> NearestMiss | None:
    """The non-qualifying, non-stale ticker nearest to `side`'s threshold (ADR-050, ADR-065).

    Distance is the score shortfall against the ticker's adjusted threshold, 0 when the score
    clears it and another rule failed. Ties use the side's ranking. The reason is the first
    failing rule. None when every ticker qualified or is stale.
    """
    side = check_side(side)
    best: tuple[tuple[float, tuple[float, float, float, float, str]], NearestMiss] | None = None
    for entry in entries:
        if entry.data_quality == STALE:
            continue
        verdict = evaluate_candidate(entry, config).side(side)
        if verdict.qualified:
            continue
        if side == "buy":
            gap = max(0.0, buy_threshold(entry, config) - entry.display_score)
        else:
            gap = max(0.0, entry.display_score - sell_threshold(entry, config))
        key = (gap, rank_key(entry, side))
        if best is None or key < best[0]:
            miss = NearestMiss(
                ticker=entry.ticker,
                side=side,
                display_score=entry.display_score,
                threshold=verdict.threshold,
                reason=verdict.reasons[0],
            )
            best = (key, miss)
    return None if best is None else best[1]


def select(
    entries: Sequence[SelectionInput],
    closes: Mapping[str, Mapping[date, float]],
    config: ScoringConfig,
    *,
    excluded: Sequence[Exclusion] = (),
    previous: Sequence[PriorPicks] = (),
) -> Selection:
    """Run the full daily selection over the scored tickers.

    * `entries`: one `SelectionInput` per scored ticker (ValueError on a repeated ticker).
      Entries whose ticker is in `excluded` are dropped (FR-412).
    * `closes`: dated daily closes per ticker for the correlation guard; a ticker without closes
      never counts as a duplicate.
    * `excluded`: tickers excluded before scoring, passed through sorted by ticker.
    * `previous`: earlier published days, most recent first, for `days_on_list`.

    Each side's candidates are ranked, walked through the correlation guard up to
    `selection.max_buys` / `selection.max_sells`, and never padded.
    """
    seen: set[str] = set()
    for entry in entries:
        if entry.ticker in seen:
            msg = f"duplicate ticker in selection input: {entry.ticker}"
            raise ValueError(msg)
        seen.add(entry.ticker)
    excluded_tickers = {e.ticker for e in excluded}
    scored = sorted(
        (e for e in entries if e.ticker not in excluded_tickers), key=lambda e: e.ticker
    )
    checks = {e.ticker: evaluate_candidate(e, config) for e in scored}
    window = config.selection.correlation_window
    empty: Mapping[date, float] = MappingProxyType({})

    def correlation(a: str, b: str) -> float | None:
        return return_correlation(closes.get(a, empty), closes.get(b, empty), window)

    by_ticker = {e.ticker: e for e in scored}
    picks: dict[Side, tuple[Pick, ...]] = {}
    also: list[AlsoQualified] = []
    misses: dict[Side, NearestMiss | None] = {}
    for side in SIDES:
        limit = config.selection.max_buys if side == "buy" else config.selection.max_sells
        qualified = [e for e in scored if checks[e.ticker].side(side).qualified]
        ranked = rank_candidates(qualified, side)
        guard = correlation_guard(
            [e.ticker for e in ranked],
            correlation,
            max_picks=limit,
            max_correlation=config.selection.correlation_max,
        )
        picks[side] = tuple(
            _pick(rank, side, by_ticker[ticker], previous)
            for rank, ticker in enumerate(guard.picked, start=1)
        )
        for dup in guard.skipped:
            entry = by_ticker[dup.ticker]
            also.append(
                AlsoQualified(
                    ticker=entry.ticker,
                    side=side,
                    display_score=entry.display_score,
                    confidence=entry.confidence,
                    duplicates=dup.duplicates,
                    correlation=dup.correlation,
                    entry=entry,
                )
            )
        misses[side] = nearest_miss(scored, side, config) if len(picks[side]) < limit else None
    return Selection(
        buys=picks["buy"],
        sells=picks["sell"],
        also_qualified=tuple(also),
        nearest_miss=MappingProxyType(misses),
        excluded=tuple(sorted(excluded, key=lambda e: (e.ticker, e.reason))),
        checks=tuple(checks[e.ticker] for e in scored),
    )


def _pick(rank: int, side: Side, entry: SelectionInput, previous: Sequence[PriorPicks]) -> Pick:
    return Pick(
        rank=rank,
        side=side,
        ticker=entry.ticker,
        display_score=entry.display_score,
        confidence=entry.confidence,
        band=entry.card.band,
        days_on_list=days_on_list(entry.ticker, side, previous),
        entry=entry,
    )
