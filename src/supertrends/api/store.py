# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""The read port the HTTP read endpoints depend on (S3-T09, ADR-072).

`supertrends.runs.reads.PgStore` implements it over Postgres; unit tests use an in-memory fake.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Protocol

from supertrends.runs.reads import (
    AnalysisRows,
    BarsData,
    PickExtras,
    RankingPage,
    SupersededRun,
    TickerInfo,
)
from supertrends.runs.service import RecommendationView, RunView, TriggerResult
from supertrends.scoring.config import ScoringConfig

__all__ = ["ReadStore"]


class ReadStore(Protocol):
    """Everything the read API needs from storage. Only `trigger` writes (a queued run)."""

    def latest_published(self) -> RunView | None: ...
    def published_for_date(self, trade_date: date) -> RunView | None: ...
    def superseded_for_date(self, trade_date: date) -> list[SupersededRun]: ...
    def picks(self, run_id: str) -> list[RecommendationView]: ...
    def pick_extras(
        self, run_id: str, picked: Sequence[str], others: Sequence[str]
    ) -> PickExtras: ...
    def rankings(
        self, run_id: str, limit: int, offset: int, group: str | None
    ) -> RankingPage | None: ...
    def ticker(self, symbol: str) -> TickerInfo | None: ...
    def analysis_rows(self, run_id: str, symbol: str) -> AnalysisRows | None: ...
    def latest_bar_date(self, symbol: str, tf: str) -> date | None: ...
    def bars(self, symbol: str, tf: str, start: date, end: date) -> BarsData: ...
    def list_runs(self, limit: int, before: str | None) -> list[RunView]: ...
    def get_run(self, run_id: str) -> RunView | None: ...
    def trigger(self, config: ScoringConfig, trade_date: date) -> TriggerResult: ...
