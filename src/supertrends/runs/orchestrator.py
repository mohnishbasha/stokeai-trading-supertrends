# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""The daily run orchestrator (FR-901 to FR-906, ARCHITECTURE sections 4.1 and 8, ADR-068).

`execute_run` takes the run advisory lock, reaps abandoned runs, inserts a `queued` run, and
drives it through `ingesting -> computing -> scoring -> selecting -> narrating -> published`.
Any error moves the run to `failed` and leaves the previous published run as latest. A second
trigger while the lock is held returns `already_running` without creating a row (ADR-021).

Each step commits its own transaction, so a killed process leaves a non-terminal row and no
published output; the next executor reaps it as `abandoned`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from supertrends.data.db import session_scope
from supertrends.data.ingest import BENCHMARKS, ingest
from supertrends.data.models import (
    BarDaily,
    FactorScore,
    Recommendation,
    Run,
    Ticker,
    TickerScore,
)
from supertrends.data.providers.base import FundamentalsProvider, MarketDataProvider
from supertrends.data.quality import Quality
from supertrends.data.snapshots import compute_and_store, read_snapshot
from supertrends.errors import IngestError
from supertrends.runs import pipeline
from supertrends.runs.narrator import (
    MinimalNarrator,
    NarratedPick,
    Narrator,
    PickContext,
    TemplateNarrator,
)
from supertrends.runs.publish import PublishItem, publish
from supertrends.runs.repo import (
    active_run,
    ensure_config_version,
    insert_run,
    reap,
    run_lock,
    scored_watchlist_symbols,
    transition,
)
from supertrends.runs.state import ErrorCode, RunState
from supertrends.scoring.config import ScoringConfig
from supertrends.scoring.factor import FactorContext, FactorRegistry
from supertrends.scoring.factors import default_registry
from supertrends.scoring.weights import NoScorableFactorsError
from supertrends.selection import Exclusion, PriorPicks, select
from supertrends.selection.ranking import Selection
from supertrends.version import get_commit, get_version

__all__ = [
    "Progress",
    "RunDeps",
    "RunOutcome",
    "RunStepError",
    "RunTerminated",
    "code_version",
    "drive_run",
    "execute_run",
    "prior_picks",
]

log = logging.getLogger(__name__)

Progress = Callable[[str, RunState], None]
OutcomeStatus = Literal["published", "failed", "already_running"]
PRIOR_PICK_DAYS = 30
_DETAIL_LIMIT = 500


class RunTerminated(BaseException):
    """Raised by the CLI SIGTERM handler; the run is failed with detail `terminated`."""


class RunStepError(Exception):
    """A step failed with a specific `runs.error_code`."""

    def __init__(self, code: ErrorCode, detail: str) -> None:
        super().__init__(detail)
        self.code = code


@dataclass(frozen=True)
class RunDeps:
    """What a run needs besides the database.

    `symbols` None means the scored watchlist. `now` feeds ingestion's "last completed
    session" (tests pin it); None means the current time.
    """

    market: MarketDataProvider
    fundamentals: FundamentalsProvider | None
    config: ScoringConfig
    narrator: Narrator = field(default_factory=TemplateNarrator)
    symbols: Sequence[str] | None = None
    registry: FactorRegistry = field(default_factory=default_registry)
    queued_timeout_seconds: int = 600
    now: datetime | None = None


@dataclass(frozen=True)
class RunOutcome:
    """The result of one trigger. `run_id` is None for `already_running`."""

    status: OutcomeStatus
    trade_date: date
    run_id: str | None = None
    summary: Mapping[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_detail: str | None = None
    active_run_id: str | None = None
    active_trade_date: date | None = None


def code_version() -> str:
    """`runs.code_version`: the package version and commit."""
    return f"{get_version()} ({get_commit()})"


@dataclass
class _Work:
    """Mutable state of one run while it executes (summary sources)."""

    run_id: str
    trade_date: date
    config_hash: str
    symbols: list[str] = field(default_factory=list)
    quality: dict[str, Quality] = field(default_factory=dict)
    excluded: list[Exclusion] = field(default_factory=list)
    provider_errors: dict[str, list[str]] = field(default_factory=dict)
    scored: list[pipeline.ScoredTicker] = field(default_factory=list)
    selection: Selection | None = None
    narrative_counts: dict[str, int] = field(default_factory=dict)
    started: float = field(default_factory=time.monotonic)

    def summary(self, deps: RunDeps) -> dict[str, Any]:
        out = pipeline.build_summary(
            trade_date=self.trade_date,
            config_hash=self.config_hash,
            scoring_version=deps.config.scoring.version,
            symbols=self.symbols,
            scored=self.scored,
            excluded=self.excluded,
            quality=self.quality,
            provider_errors=self.provider_errors,
            selection=self.selection,
        )
        out.update(self.narrative_counts)
        out["duration_seconds"] = round(time.monotonic() - self.started, 3)
        return out


def _step(engine: Engine, work: _Work, state: RunState, progress: Progress | None) -> None:
    with session_scope(engine) as session:
        transition(session, work.run_id, state)
    if progress is not None:
        progress(work.run_id, state)


def _ingest(engine: Engine, deps: RunDeps, work: _Work) -> None:
    if deps.symbols is None:
        with session_scope(engine) as session:
            work.symbols = scored_watchlist_symbols(session)
    else:
        work.symbols = sorted({s.strip().upper() for s in deps.symbols if s.strip()})
    wanted = sorted({*work.symbols, *BENCHMARKS})
    try:
        result = ingest(
            engine, deps.market, deps.fundamentals, wanted, as_of=work.trade_date, now=deps.now
        )
    except IngestError as exc:
        raise RunStepError(ErrorCode.PROVIDER_UNAVAILABLE, str(exc)) from exc
    by_symbol = {r.symbol: r for r in result.results}
    work.provider_errors = {r.symbol: list(r.errors) for r in result.results if r.errors}
    broken = [b for b in BENCHMARKS if by_symbol[b].status in ("error", "unresolved", "skipped")]
    if broken:
        detail = f"benchmark data unavailable: {', '.join(broken)}"
        raise RunStepError(ErrorCode.BENCHMARK_UNAVAILABLE, detail)
    unresolved = [s for s in work.symbols if by_symbol[s].status == "unresolved"]
    with session_scope(engine) as session:
        bar_dates: dict[str, list[date]] = {}
        for symbol, day in session.execute(
            sa.select(BarDaily.symbol, BarDaily.date)
            .where(BarDaily.symbol.in_(work.symbols), BarDaily.date <= work.trade_date)
            .order_by(BarDaily.symbol, BarDaily.date)
        ):
            bar_dates.setdefault(symbol, []).append(day)
    quality, excluded = pipeline.classify_universe(
        work.symbols, bar_dates, work.trade_date, unresolved=unresolved
    )
    work.quality = quality
    work.excluded = list(excluded)


def _remaining(work: _Work) -> list[str]:
    gone = {e.ticker for e in work.excluded}
    return [s for s in work.symbols if s not in gone]


def _compute(engine: Engine, deps: RunDeps, work: _Work) -> dict[str, Mapping[str, Any]]:
    snapshots: dict[str, Mapping[str, Any]] = {}
    with session_scope(engine) as session:
        result = compute_and_store(
            session, work.run_id, _remaining(work), deps.config, work.trade_date
        )
        for symbol, reason in sorted(result.skipped.items()):
            work.excluded.append(Exclusion(symbol, reason))
        for symbol in _remaining(work):
            doc = read_snapshot(session, work.run_id, symbol)
            if doc is not None:
                snapshots[symbol] = doc
    return snapshots


def _score(
    engine: Engine, deps: RunDeps, work: _Work, snapshots: Mapping[str, Mapping[str, Any]]
) -> None:
    factors = deps.registry.ordered(deps.config)
    context = FactorContext(config=deps.config, as_of=work.trade_date)
    for symbol in _remaining(work):
        try:
            work.scored.append(
                pipeline.score_one(
                    symbol, snapshots[symbol], factors, context, work.quality[symbol]
                )
            )
        except NoScorableFactorsError:
            work.excluded.append(Exclusion(symbol, pipeline.NO_DATA))
    work.excluded.sort(key=lambda e: e.ticker)
    ranks = pipeline.rank_overall(work.scored)
    with session_scope(engine) as session:
        known = set(
            session.scalars(sa.select(Ticker.symbol).where(Ticker.symbol.in_(work.symbols)))
        )
        rows = [
            pipeline.ticker_score_row(work.run_id, s, ranks[s.ticker], deps.config)
            for s in work.scored
        ]
        rows += [
            pipeline.excluded_row(
                work.run_id, e, work.quality.get(e.ticker, "insufficient_history")
            )
            for e in work.excluded
            if e.ticker in known
        ]
        if rows:
            for row in rows:
                session.execute(insert(TickerScore).values(**row))
        factor_rows = [r for s in work.scored for r in pipeline.factor_score_rows(work.run_id, s)]
        if factor_rows:
            session.execute(insert(FactorScore), factor_rows)


def _closes(engine: Engine, deps: RunDeps, work: _Work) -> dict[str, dict[date, float]]:
    days = deps.config.selection.correlation_window * 2 + 30
    start = work.trade_date - timedelta(days=days)
    closes: dict[str, dict[date, float]] = {}
    with session_scope(engine) as session:
        for symbol, day, close in session.execute(
            sa.select(BarDaily.symbol, BarDaily.date, BarDaily.close).where(
                BarDaily.symbol.in_([s.ticker for s in work.scored]),
                BarDaily.date > start,
                BarDaily.date <= work.trade_date,
            )
        ):
            closes.setdefault(symbol, {})[day] = close
    return closes


def prior_picks(engine: Engine, trade_date: date, days: int = PRIOR_PICK_DAYS) -> list[PriorPicks]:
    """Published picks of the current runs before `trade_date`, most recent first."""
    with session_scope(engine) as session:
        runs = session.execute(
            sa.select(Run.id, Run.trade_date)
            .where(
                Run.trade_date < trade_date,
                Run.published_at.is_not(None),
                Run.superseded_by.is_(None),
            )
            .order_by(Run.trade_date.desc())
            .limit(days)
        ).all()
        recs = session.execute(
            sa.select(Recommendation.run_id, Recommendation.symbol, Recommendation.side).where(
                Recommendation.run_id.in_([r.id for r in runs])
            )
        ).all()
    by_run: dict[str, dict[str, set[str]]] = {r.id: {"buy": set(), "sell": set()} for r in runs}
    for rec in recs:
        by_run[rec.run_id][rec.side].add(rec.symbol)
    return [
        PriorPicks(frozenset(by_run[r.id]["buy"]), frozenset(by_run[r.id]["sell"])) for r in runs
    ]


def _select(engine: Engine, deps: RunDeps, work: _Work) -> None:
    work.selection = select(
        [s.entry for s in work.scored],
        _closes(engine, deps, work),
        deps.config,
        excluded=work.excluded,
        previous=prior_picks(engine, work.trade_date),
    )


def _narrate(deps: RunDeps, work: _Work) -> list[PublishItem]:
    assert work.selection is not None  # noqa: S101 - selecting always runs first
    by_ticker = {s.ticker: s for s in work.scored}
    counts = {
        "narrative_llm": 0,
        "narrative_template": 0,
        "narrative_none": 0,
        "narrative_errors": 0,
    }
    items = []
    for pick in (*work.selection.buys, *work.selection.sells):
        st = by_ticker[pick.ticker]
        ctx = PickContext(
            pick=pick,
            trade_date=work.trade_date,
            snapshot=st.snapshot,
            factor_results=st.results,
            config=deps.config,
            selection=work.selection,
        )
        try:
            narrated = deps.narrator.narrate(ctx)
        except Exception:
            log.exception("narrator failed for %s; using the minimal narrator", pick.ticker)
            counts["narrative_errors"] += 1
            narrated = MinimalNarrator().narrate(ctx)
        _count_narrative(counts, narrated)
        items.append(PublishItem(pick=pick, narrated=narrated))
    work.narrative_counts = counts
    return items


def _count_narrative(counts: dict[str, int], narrated: NarratedPick) -> None:
    if narrated.narrative is None:
        counts["narrative_none"] += 1
    else:
        key = f"narrative_{narrated.narrative.source}"
        counts[key] = counts.get(key, 0) + 1


def _fail(engine: Engine, work: _Work, deps: RunDeps, code: str, detail: str) -> None:
    try:
        with session_scope(engine) as session:
            transition(
                session,
                work.run_id,
                RunState.FAILED,
                detail={"error_code": code},
                error_code=code,
                error_detail=detail[:_DETAIL_LIMIT],
                summary=work.summary(deps),
            )
    except (SQLAlchemyError, ValueError, LookupError):
        log.exception("could not mark run %s failed; the next executor reaps it", work.run_id)


def drive_run(  # noqa: PLR0913 - keyword-only run identity and callback
    engine: Engine,
    deps: RunDeps,
    run_id: str,
    *,
    trade_date: date,
    config_hash: str,
    progress: Progress | None = None,
) -> RunOutcome:
    """Execute an existing `queued` run to `published` or `failed`. The caller holds the lock.

    Errors become a `failed` outcome; RunTerminated and KeyboardInterrupt fail the run and are
    re-raised.
    """
    work = _Work(run_id=run_id, trade_date=trade_date, config_hash=config_hash)
    try:
        _step(engine, work, RunState.INGESTING, progress)
        _ingest(engine, deps, work)
        _step(engine, work, RunState.COMPUTING, progress)
        snapshots = _compute(engine, deps, work)
        _step(engine, work, RunState.SCORING, progress)
        _score(engine, deps, work, snapshots)
        _step(engine, work, RunState.SELECTING, progress)
        _select(engine, deps, work)
        _step(engine, work, RunState.NARRATING, progress)
        items = _narrate(deps, work)
        summary = work.summary(deps)
        publish(engine, run_id, trade_date, items, summary)
    except RunStepError as exc:
        _fail(engine, work, deps, exc.code, str(exc))
        return _failed(work, deps, exc.code, str(exc), progress)
    except Exception as exc:  # any unhandled step error fails the run (section 4.1)
        log.exception("run %s failed", run_id)
        detail = f"{type(exc).__name__}: {exc}"
        _fail(engine, work, deps, ErrorCode.INTERNAL, detail)
        return _failed(work, deps, ErrorCode.INTERNAL, detail, progress)
    except BaseException as exc:
        detail = "terminated" if isinstance(exc, RunTerminated) else "interrupted"
        _fail(engine, work, deps, ErrorCode.INTERNAL, detail)
        raise
    if progress is not None:
        progress(run_id, RunState.PUBLISHED)
    return RunOutcome(status="published", trade_date=trade_date, run_id=run_id, summary=summary)


def _failed(
    work: _Work, deps: RunDeps, code: str, detail: str, progress: Progress | None
) -> RunOutcome:
    if progress is not None:
        progress(work.run_id, RunState.FAILED)
    return RunOutcome(
        status="failed",
        trade_date=work.trade_date,
        run_id=work.run_id,
        summary=work.summary(deps),
        error_code=code,
        error_detail=detail[:_DETAIL_LIMIT],
    )


def _already_running(engine: Engine, trade_date: date) -> RunOutcome:
    with session_scope(engine) as session:
        active = active_run(session)
    return RunOutcome(
        status="already_running",
        trade_date=trade_date,
        active_run_id=None if active is None else active[0],
        active_trade_date=None if active is None else active[1],
    )


def execute_run(
    engine: Engine,
    deps: RunDeps,
    *,
    trade_date: date,
    trigger: str = "cli",
    progress: Progress | None = None,
) -> RunOutcome:
    """Run `trade_date` inline under the run lock (CLI and CronJob path, FR-901 to FR-904).

    `trade_date` must already be validated (`runs.dates.resolve_trade_date`). Returns
    `already_running` when another process holds the lock or another run is active.
    """
    with run_lock(engine) as lock:
        if lock is None:
            return _already_running(engine, trade_date)
        try:
            with session_scope(engine) as session:
                reap(session, queued_timeout_seconds=deps.queued_timeout_seconds)
                digest = ensure_config_version(session, deps.config)
                session.flush()
                run_id = insert_run(
                    session,
                    trade_date=trade_date,
                    trigger=trigger,
                    config_hash=digest,
                    code_version=code_version(),
                )
        except IntegrityError:
            return _already_running(engine, trade_date)
        if progress is not None:
            progress(run_id, RunState.QUEUED)
        return drive_run(
            engine, deps, run_id, trade_date=trade_date, config_hash=digest, progress=progress
        )
