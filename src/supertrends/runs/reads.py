# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Read models and the Postgres-backed read store behind the read API (S3-T09, ADR-072).

`PgStore` is the production implementation of `supertrends.api.store.ReadStore`: it answers the
HTTP read endpoints from the stored run, ranking, factor, snapshot, recommendation and bar rows.
Everything is read-only except `trigger`, which only inserts a `queued` run (ADR-020). Readers
follow the read rule of `runs.service`: only current published runs are ever served as results.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import numpy as np
import sqlalchemy as sa
from sqlalchemy import Engine

from supertrends.data.db import session_scope
from supertrends.data.models import (
    BarDaily,
    BarIntraday,
    FactorScore,
    IndicatorSnapshot,
    Run,
    Ticker,
    TickerScore,
    WatchlistGroup,
    WatchlistGroupMember,
    WatchlistItem,
)
from supertrends.indicators.supertrend import supertrend
from supertrends.runs import service
from supertrends.runs.overlays import (
    OhlcvSeries,
    compute_overlays,
    ribbon,
    weekly_series,
)
from supertrends.runs.service import RecommendationView, RunView, TriggerResult
from supertrends.scoring.config import ScoringConfig

__all__ = [
    "AnalysisRows",
    "BarRow",
    "BarsData",
    "FactorRow",
    "PgStore",
    "PickExtras",
    "RankingPage",
    "RankingRow",
    "ScoreRow",
    "SupersededRun",
    "TickerInfo",
]

RIBBON_HISTORY_BARS = 400
ATR_DECIMALS = 2


@dataclass(frozen=True)
class SupersededRun:
    """An earlier published run of the same date, replaced by a later one."""

    id: str
    published_at: datetime | None


@dataclass(frozen=True)
class PickExtras:
    """Per-ticker values the pick cards need that the evidence document does not carry.

    `expected_move` is the daily ATR (price units), `ribbon` the last 10 daily Supertrend
    directions, `scores` the (display score, confidence) of the also-qualified tickers.
    """

    expected_move: Mapping[str, float | None]
    ribbon: Mapping[str, str]
    scores: Mapping[str, tuple[float, float]]


@dataclass(frozen=True)
class RankingRow:
    """One scored ticker of a run, in overall rank order."""

    rank: int
    ticker: str
    display_score: float
    band: str
    confidence: float
    composite: float
    regime: str
    st_dir_d: int | None
    st_dir_w: int | None
    bars_since_flip: int | None
    candidate: str | None
    flags: list[str]
    groups: list[str]


@dataclass(frozen=True)
class RankingPage:
    """A page of ranking rows and the total number of scored tickers (after the group filter)."""

    total: int
    rows: list[RankingRow]


@dataclass(frozen=True)
class TickerInfo:
    """A known ticker (watchlist member, benchmark, or scored in some run)."""

    symbol: str
    name: str | None


@dataclass(frozen=True)
class ScoreRow:
    """A `ticker_scores` row (scored or excluded)."""

    status: str
    exclusion_reason: str | None
    data_quality: str
    composite: float | None
    display_score: float | None
    band: str | None
    confidence: float | None
    regime: str | None
    st_dir_d: int | None
    st_dir_w: int | None
    bars_since_flip: int | None
    st_line: float | None
    buy_threshold: float | None
    sell_threshold: float | None
    candidate: str | None
    weights: Mapping[str, Any] | None
    adjustments: list[Any]
    flags: list[Any]


@dataclass(frozen=True)
class FactorRow:
    """A `factor_scores` row; `items` are the stored evidence items (name, value, unit, reason)."""

    id: str
    score: float | None
    weight: float
    contribution: float
    quality: str
    items: list[Mapping[str, Any]]


@dataclass(frozen=True)
class AnalysisRows:
    """The stored rows of one ticker in one run."""

    score: ScoreRow
    factors: list[FactorRow]
    snapshot: Mapping[str, Any] | None


@dataclass(frozen=True)
class BarRow:
    """One bar; `t` is the session date (daily, weekly) or the UTC start (5-minute)."""

    t: date | datetime
    o: float
    h: float
    l: float  # noqa: E741 - the API field is `l`
    c: float
    v: int


@dataclass(frozen=True)
class BarsData:
    """Bars in range and the overlay series aligned to them."""

    bars: list[BarRow]
    overlays: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def _f(value: Any) -> float | None:
    return None if value is None else float(value)


class PgStore:
    """Read store over one engine and the active scoring config."""

    def __init__(self, engine: Engine, config: ScoringConfig) -> None:
        self._engine = engine
        self._config = config

    # runs --------------------------------------------------------------------------------

    def latest_published(self) -> RunView | None:
        """The current published run with the greatest trade date."""
        return service.latest_published_run(self._engine)

    def published_for_date(self, trade_date: date) -> RunView | None:
        """The current published run of `trade_date`."""
        return service.published_run_for_date(self._engine, trade_date)

    def superseded_for_date(self, trade_date: date) -> list[SupersededRun]:
        """Earlier published runs of the date, oldest first."""
        with session_scope(self._engine) as session:
            rows = session.execute(
                sa.select(Run.id, Run.published_at)
                .where(
                    Run.trade_date == trade_date,
                    Run.published_at.is_not(None),
                    Run.superseded_by.is_not(None),
                )
                .order_by(Run.published_at, Run.id)
            ).all()
        return [SupersededRun(r.id, r.published_at) for r in rows]

    def list_runs(self, limit: int, before: str | None) -> list[RunView]:
        """Runs newest first."""
        return service.list_runs(self._engine, limit=limit, before=before)

    def get_run(self, run_id: str) -> RunView | None:
        """One run with its transitions."""
        return service.get_run(self._engine, run_id)

    def trigger(self, config: ScoringConfig, trade_date: date) -> TriggerResult:
        """Insert a queued run (the worker executes it)."""
        return service.trigger_run(self._engine, config, trade_date=trade_date, trigger="api")

    # picks -------------------------------------------------------------------------------

    def picks(self, run_id: str) -> list[RecommendationView]:
        """The run's published picks."""
        return service.recommendations_for_run(self._engine, run_id)

    def pick_extras(self, run_id: str, picked: Sequence[str], others: Sequence[str]) -> PickExtras:
        """ATR, ribbon and scores for the pick cards."""
        moves: dict[str, float | None] = {}
        ribbons: dict[str, str] = {}
        scores: dict[str, tuple[float, float]] = {}
        with session_scope(self._engine) as session:
            trade_date = session.scalar(sa.select(Run.trade_date).where(Run.id == run_id))
            for symbol in picked:
                doc = session.scalar(
                    sa.select(IndicatorSnapshot.values).where(
                        IndicatorSnapshot.run_id == run_id, IndicatorSnapshot.symbol == symbol
                    )
                )
                atr = None if doc is None else (doc.get("daily") or {}).get("atr")
                moves[symbol] = None if atr is None else round(float(atr), ATR_DECIMALS)
                ribbons[symbol] = self._ribbon(session, symbol, trade_date)
            if others:
                for row in session.execute(
                    sa.select(
                        TickerScore.symbol, TickerScore.display_score, TickerScore.confidence
                    ).where(TickerScore.run_id == run_id, TickerScore.symbol.in_(others))
                ):
                    if row.display_score is not None and row.confidence is not None:
                        scores[row.symbol] = (float(row.display_score), float(row.confidence))
        return PickExtras(moves, ribbons, scores)

    def _ribbon(self, session: Any, symbol: str, trade_date: date | None) -> str:
        if trade_date is None:
            return ""
        rows = session.execute(
            sa.select(BarDaily.high, BarDaily.low, BarDaily.close)
            .where(BarDaily.symbol == symbol, BarDaily.date <= trade_date)
            .order_by(BarDaily.date.desc())
            .limit(RIBBON_HISTORY_BARS)
        ).all()[::-1]
        if not rows:
            return ""
        cfg = self._config.supertrend
        st = supertrend(
            np.array([r.high for r in rows], dtype=np.float64),
            np.array([r.low for r in rows], dtype=np.float64),
            np.array([r.close for r in rows], dtype=np.float64),
            cfg.atr_length,
            cfg.factor,
        )
        return ribbon(st.direction)

    # rankings and analysis ---------------------------------------------------------------

    def rankings(
        self, run_id: str, limit: int, offset: int, group: str | None
    ) -> RankingPage | None:
        """A page of the ranking; None when `group` is not a known group slug."""
        scored = sa.and_(TickerScore.run_id == run_id, TickerScore.status == "scored")
        with session_scope(self._engine) as session:
            where = scored
            if group is not None:
                gid = session.scalar(
                    sa.select(WatchlistGroup.id).where(WatchlistGroup.slug == group)
                )
                if gid is None:
                    return None
                members = sa.select(WatchlistGroupMember.symbol).where(
                    WatchlistGroupMember.group_id == gid
                )
                where = sa.and_(scored, TickerScore.symbol.in_(members))
            total = session.scalar(sa.select(sa.func.count()).select_from(TickerScore).where(where))
            rows = session.scalars(
                sa.select(TickerScore)
                .where(where)
                .order_by(TickerScore.rank_overall, TickerScore.symbol)
                .limit(limit)
                .offset(offset)
            ).all()
            slugs: dict[str, list[str]] = {}
            for symbol, slug in session.execute(
                sa.select(WatchlistGroupMember.symbol, WatchlistGroup.slug)
                .join(WatchlistGroup, WatchlistGroup.id == WatchlistGroupMember.group_id)
                .where(WatchlistGroupMember.symbol.in_([r.symbol for r in rows]))
                .order_by(WatchlistGroup.position, WatchlistGroup.slug)
            ):
                slugs.setdefault(symbol, []).append(slug)
        return RankingPage(
            int(total or 0),
            [
                RankingRow(
                    rank=r.rank_overall or 0,
                    ticker=r.symbol,
                    display_score=float(r.display_score or 0),
                    band=r.band or "",
                    confidence=float(r.confidence or 0),
                    composite=float(r.composite or 0),
                    regime=r.regime or "",
                    st_dir_d=r.st_dir_d,
                    st_dir_w=r.st_dir_w,
                    bars_since_flip=r.bars_since_flip,
                    candidate=r.candidate,
                    flags=[str(f) for f in r.flags],
                    groups=slugs.get(r.symbol, []),
                )
                for r in rows
            ],
        )

    def ticker(self, symbol: str) -> TickerInfo | None:
        """The ticker when it is on the watchlist, a benchmark, or was ever scored."""
        with session_scope(self._engine) as session:
            row = session.execute(
                sa.select(Ticker.symbol, Ticker.name, Ticker.is_benchmark).where(
                    Ticker.symbol == symbol
                )
            ).first()
            if row is None:
                return None
            known = row.is_benchmark or session.scalar(
                sa.select(
                    sa.or_(
                        sa.exists().where(WatchlistItem.symbol == symbol),
                        sa.exists().where(TickerScore.symbol == symbol),
                    )
                )
            )
            return TickerInfo(row.symbol, row.name) if known else None

    def analysis_rows(self, run_id: str, symbol: str) -> AnalysisRows | None:
        """The ticker's score row, factor rows and snapshot in the run; None without a score row."""
        with session_scope(self._engine) as session:
            score = session.get(TickerScore, (run_id, symbol))
            if score is None:
                return None
            factors = session.scalars(
                sa.select(FactorScore).where(
                    FactorScore.run_id == run_id, FactorScore.symbol == symbol
                )
            ).all()
            snapshot = session.scalar(
                sa.select(IndicatorSnapshot.values).where(
                    IndicatorSnapshot.run_id == run_id, IndicatorSnapshot.symbol == symbol
                )
            )
        return AnalysisRows(
            score=ScoreRow(
                status=score.status,
                exclusion_reason=score.exclusion_reason,
                data_quality=score.data_quality,
                composite=score.composite,
                display_score=_f(score.display_score),
                band=score.band,
                confidence=score.confidence,
                regime=score.regime,
                st_dir_d=score.st_dir_d,
                st_dir_w=score.st_dir_w,
                bars_since_flip=score.bars_since_flip,
                st_line=score.st_line,
                buy_threshold=_f(score.buy_threshold),
                sell_threshold=_f(score.sell_threshold),
                candidate=score.candidate,
                weights=score.weights,
                adjustments=list(score.adjustments),
                flags=list(score.flags),
            ),
            factors=[
                FactorRow(
                    id=f.factor_id,
                    score=f.score,
                    weight=f.weight,
                    contribution=f.contribution,
                    quality=f.quality,
                    items=list((f.evidence or {}).get("items", [])),
                )
                for f in factors
            ],
            snapshot=snapshot,
        )

    # bars --------------------------------------------------------------------------------

    def latest_bar_date(self, symbol: str, tf: str) -> date | None:
        """The latest stored bar date for the timeframe."""
        with session_scope(self._engine) as session:
            if tf == "5m":
                ts = session.scalar(
                    sa.select(sa.func.max(BarIntraday.ts)).where(BarIntraday.symbol == symbol)
                )
                return None if ts is None else ts.astimezone(UTC).date() if ts.tzinfo else ts.date()
            return session.scalar(
                sa.select(sa.func.max(BarDaily.date)).where(BarDaily.symbol == symbol)
            )

    def bars(self, symbol: str, tf: str, start: date, end: date) -> BarsData:
        """Bars in [start, end] with overlays computed over the full history up to `end`."""
        if tf == "5m":
            return self._intraday(symbol, start, end)
        with session_scope(self._engine) as session:
            rows = session.execute(
                sa.select(
                    BarDaily.date,
                    BarDaily.open,
                    BarDaily.high,
                    BarDaily.low,
                    BarDaily.close,
                    BarDaily.volume,
                )
                .where(BarDaily.symbol == symbol, BarDaily.date <= end)
                .order_by(BarDaily.date)
            ).all()
        if not rows:
            return BarsData([], self._empty())
        series = OhlcvSeries(
            [r.date for r in rows],
            np.array([r.open for r in rows], dtype=np.float64),
            np.array([r.high for r in rows], dtype=np.float64),
            np.array([r.low for r in rows], dtype=np.float64),
            np.array([r.close for r in rows], dtype=np.float64),
            np.array([float(r.volume) for r in rows], dtype=np.float64),
        )
        if tf == "1w":
            series = weekly_series(series)
        overlays = compute_overlays(series, self._config)
        low, high = start.isoformat(), end.isoformat()
        kept = {
            key: [p for p in points if low <= p["t"] <= high] for key, points in overlays.items()
        }
        bars = [
            BarRow(
                series.dates[i],
                float(series.open[i]),
                float(series.high[i]),
                float(series.low[i]),
                float(series.close[i]),
                int(series.volume[i]),
            )
            for i in range(len(series.dates))
            if start <= series.dates[i] <= end
        ]
        return BarsData(bars, kept)

    def _empty(self) -> dict[str, list[dict[str, Any]]]:
        keys = ["supertrend", *(f"sma_{p}" for p in self._config.sma.periods)]
        return {k: [] for k in [*keys, "ripster_c2", "ripster_c3"]}

    def _intraday(self, symbol: str, start: date, end: date) -> BarsData:
        first = datetime.combine(start, time(), tzinfo=UTC)
        limit = datetime.combine(end + timedelta(days=1), time(), tzinfo=UTC)
        with session_scope(self._engine) as session:
            rows = session.execute(
                sa.select(
                    BarIntraday.ts,
                    BarIntraday.open,
                    BarIntraday.high,
                    BarIntraday.low,
                    BarIntraday.close,
                    BarIntraday.volume,
                )
                .where(
                    BarIntraday.symbol == symbol, BarIntraday.ts >= first, BarIntraday.ts < limit
                )
                .order_by(BarIntraday.ts)
            ).all()
        bars = [
            BarRow(
                r.ts if r.ts.tzinfo else r.ts.replace(tzinfo=UTC),
                r.open,
                r.high,
                r.low,
                r.close,
                int(r.volume),
            )
            for r in rows
        ]
        return BarsData(bars, self._empty())
