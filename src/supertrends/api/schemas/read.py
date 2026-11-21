# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Response and request models of the read API (ARCHITECTURE 6.1, FR-801 to FR-807, S3-T09).

Every payload that carries a pick or a score also carries the disclaimer (FR-805). These models
define the committed OpenAPI document, so field names are part of the public contract.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "AlsoQualified",
    "AnalysisResponse",
    "BarsResponse",
    "ConfigRef",
    "ConfigResponse",
    "Excluded",
    "NearestMiss",
    "Pick",
    "RankingsResponse",
    "RecommendationsResponse",
    "RunDetail",
    "RunListResponse",
    "RunTriggerRequest",
    "RunTriggerResponse",
]


class _Out(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class ConfigRef(_Out):
    """The scoring config a run used. `version` is null when it is not the active config."""

    version: int | None
    hash: str


class Excluded(_Out):
    """A ticker left out of the run and why."""

    ticker: str
    reason: str


class SupertrendBlock(_Out):
    """Supertrend state of the pick or ticker."""

    dir_d: int | None = None
    dir_w: int | None = None
    bars_since_flip: int | None = None
    line: float | None = None
    distance_atr: float | None = None


class Invalidation(_Out):
    """The level that invalidates the pick and the rule."""

    level: float | None = None
    rule: str | None = None


class TopFactor(_Out):
    """One of the factors that moved the score most."""

    id: str
    contribution: float


class NarrativeOut(_Out):
    """Stored narrative text and provenance."""

    text: str
    source: str
    model: str | None = None


class Pick(_Out):
    """A published pick (FR-801)."""

    recommendation_id: str
    side: Literal["buy", "sell"]
    rank: int
    ticker: str
    display_score: float
    band: str
    confidence: int
    regime: str | None = None
    supertrend: SupertrendBlock
    invalidation: Invalidation
    top_factors: list[TopFactor]
    ribbon: str
    flags: list[str]
    days_on_list: int | None = None
    expected_1d_move: float | None = None
    levels: dict[str, Any] | None = None
    narrative: NarrativeOut | None = None
    entry_price: float | None = None
    entry_date: dt.date | None = None


class AlsoQualified(_Out):
    """A ticker that qualified but duplicates a pick (ADR-007 correlation limit)."""

    ticker: str
    side: str
    display_score: float | None = None
    confidence: int | None = None
    duplicates: str | None = None
    correlation: float | None = None


class NearestMiss(_Out):
    """The closest ticker to a threshold when a side has no pick."""

    ticker: str
    display_score: float
    reason: str


class NearestMisses(_Out):
    """Nearest miss per side."""

    buy: NearestMiss | None = None
    sell: NearestMiss | None = None


class SummaryCounts(_Out):
    """Run counts shown with the picks."""

    tickers_total: int = 0
    tickers_scored: int = 0
    tickers_excluded: int = 0
    narrative_llm: int = 0
    narrative_template: int = 0
    duration_seconds: float | None = None


class SupersededOut(_Out):
    """An earlier published run of the same date."""

    id: str
    published_at: dt.datetime | None = None


class RecommendationsResponse(_Out):
    """Picks of one trade date (`GET /recommendations/latest` and `GET /recommendations`)."""

    date: dt.date
    run_id: str
    published_at: dt.datetime | None
    market_regime: str | None
    config: ConfigRef
    buys: list[Pick]
    sells: list[Pick]
    also_qualified: list[AlsoQualified]
    nearest_miss: NearestMisses
    excluded: list[Excluded]
    summary: SummaryCounts
    superseded_runs: list[SupersededOut]
    disclaimer: str


class RankingItem(_Out):
    """One ranked ticker."""

    rank: int
    ticker: str
    display_score: float
    band: str
    confidence: int
    composite: float
    regime: str
    st_dir_d: int | None
    st_dir_w: int | None
    bars_since_flip: int | None
    candidate: str | None
    flags: list[str]
    groups: list[str]
    picked: Literal["buy", "sell", "also_qualified"] | None


class RankingsResponse(_Out):
    """A page of the run's ranking, with data-quality exclusions."""

    date: dt.date
    run_id: str
    total: int
    limit: int
    offset: int
    items: list[RankingItem]
    excluded: list[Excluded]
    disclaimer: str


class FactorOut(_Out):
    """One factor's score and its stated reasons."""

    id: str
    score: float | None
    base_weight: float | None
    weight: float | None
    contribution: float
    quality: str
    reasons: list[str]


class Thresholds(_Out):
    """The buy and sell display-score thresholds applied to the ticker."""

    buy: float | None
    sell: float | None


class RipsterBlock(_Out):
    """Ripster EMA cloud state (Factor 12)."""

    bias: float | None = None
    stack: float | None = None
    bars_since_stack_flip: float | None = None
    c2_dir: float | None = None
    c3_dir: float | None = None
    c3_top: float | None = None
    c3_bot: float | None = None
    dir_w: float | None = None


class PickedRef(_Out):
    """The pick the ticker became in this run."""

    side: Literal["buy", "sell"]
    rank: int
    recommendation_id: str


class AnalysisResponse(_Out):
    """Full factor breakdown of one ticker in one run (FR-803)."""

    ticker: str
    name: str | None
    date: dt.date
    run_id: str
    market_regime: str | None
    config: ConfigRef
    status: Literal["scored", "excluded"]
    exclusion_reason: str | None
    data_quality: str | None
    display_score: float | None
    band: str | None
    confidence: int | None
    composite: float | None
    regime: str | None
    candidate: str | None
    thresholds: Thresholds
    factors: list[FactorOut]
    adjustments: list[Any]
    flags: list[Any]
    supertrend: SupertrendBlock
    ripster: RipsterBlock
    expected_1d_move: float | None
    picked: PickedRef | None
    narrative: NarrativeOut | None
    disclaimer: str


class BarOut(_Out):
    """One OHLCV bar. `t` is a date (1d, 1w) or a UTC timestamp (5m)."""

    t: str
    o: float
    h: float
    l: float  # noqa: E741 - the API field is `l`
    c: float
    v: int


class BarsResponse(_Out):
    """Bars and chart overlays for a ticker (FR-804). Overlay points carry `t` plus value fields."""

    ticker: str
    tf: Literal["1d", "1w", "5m"]
    from_: dt.date | None = Field(alias="from")
    to: dt.date | None
    bars: list[BarOut]
    overlays: dict[str, list[dict[str, float | int | str]]]


class RunListItem(_Out):
    """A run in the list view."""

    id: str
    trade_date: dt.date
    state: str
    trigger: str
    created_at: dt.datetime
    finished_at: dt.datetime | None
    published_at: dt.datetime | None
    superseded_by: str | None
    error_code: str | None
    picks: dict[str, int]
    duration_seconds: float | None


class RunListResponse(_Out):
    """Runs newest first; pass `next_before` as `before` for the next page."""

    items: list[RunListItem]
    next_before: str | None


class TransitionOut(_Out):
    """One state transition."""

    seq: int
    from_: str | None = Field(alias="from")
    to: str
    at: dt.datetime


class NarrativeCounts(_Out):
    """Narratives by source."""

    llm: int = 0
    template: int = 0


class RunSummaryOut(_Out):
    """The stored run summary (FR-906)."""

    tickers_total: int | None = None
    tickers_scored: int | None = None
    tickers_excluded: int | None = None
    excluded: list[Excluded] = Field(default_factory=list)
    buys: list[str] = Field(default_factory=list)
    sells: list[str] = Field(default_factory=list)
    narrative: NarrativeCounts = Field(default_factory=NarrativeCounts)
    duration_seconds: float | None = None


class RunDetail(_Out):
    """One run with its state history."""

    id: str
    trade_date: dt.date
    state: str
    trigger: str
    config_hash: str
    code_version: str
    market_regime: str | None
    created_at: dt.datetime
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    published_at: dt.datetime | None
    superseded_by: str | None
    error_code: str | None
    error_detail: str | None
    summary: RunSummaryOut
    transitions: list[TransitionOut]


class RunTriggerRequest(BaseModel):
    """Body of `POST /runs`; no date means today's completed session."""

    model_config = ConfigDict(extra="forbid")

    date: dt.date | None = None


class RunTriggerResponse(_Out):
    """A queued run (202)."""

    run_id: str
    state: Literal["queued"]
    trade_date: dt.date


class MarketClosedResponse(_Out):
    """No session to run today (200)."""

    run_id: None = None
    state: Literal["market_closed"] = "market_closed"


class ConfigResponse(_Out):
    """The active scoring config."""

    version: int
    hash: str
    document: dict[str, Any]
    loaded_at: dt.datetime
