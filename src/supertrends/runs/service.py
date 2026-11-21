# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Run service functions for the API, MCP and worker (ADR-020, ADR-021, ADR-066).

Triggering (`trigger_run`) only inserts a `queued` row; a worker executes it with
`run_next_queued`. Readers follow the read rule: "latest" is the current published run with the
greatest trade date (`published_at IS NOT NULL AND superseded_by IS NULL`), so nothing of a
failed, running, or superseded run is ever served as current.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supertrends.data.db import session_scope
from supertrends.data.models import Narrative, Recommendation, Run, RunTransition
from supertrends.runs.narrator import DISCLAIMER
from supertrends.runs.orchestrator import (
    Progress,
    RunDeps,
    RunOutcome,
    code_version,
    drive_run,
)
from supertrends.runs.repo import (
    active_run,
    ensure_config_version,
    insert_run,
    reap,
    run_lock,
)
from supertrends.runs.state import RunState
from supertrends.scoring.config import ScoringConfig

__all__ = [
    "DEFAULT_LIST_LIMIT",
    "NarrativeView",
    "RecommendationView",
    "RunView",
    "TransitionView",
    "TriggerResult",
    "get_run",
    "latest_published_run",
    "list_runs",
    "published_run_for_date",
    "recommendations_for_run",
    "run_next_queued",
    "trigger_run",
]

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 200


@dataclass(frozen=True)
class TriggerResult:
    """`queued` with the new `run_id`, or `already_running` with the active run."""

    status: Literal["queued", "already_running"]
    trade_date: date
    run_id: str | None = None
    active_run_id: str | None = None
    active_trade_date: date | None = None


@dataclass(frozen=True)
class TransitionView:
    """One `run_transitions` row."""

    seq: int
    from_state: str | None
    to_state: str
    at: datetime
    detail: Mapping[str, Any]


@dataclass(frozen=True)
class RunView:
    """A `runs` row with its transitions (empty in list views)."""

    id: str
    trade_date: date
    state: str
    trigger: str
    config_hash: str
    code_version: str
    market_regime: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    published_at: datetime | None
    superseded_by: str | None
    error_code: str | None
    error_detail: str | None
    summary: Mapping[str, Any]
    transitions: tuple[TransitionView, ...] = ()


@dataclass(frozen=True)
class NarrativeView:
    """A stored narrative."""

    text: str
    source: str
    model: str | None
    prompt_version: str


@dataclass(frozen=True)
class RecommendationView:
    """A published pick with its evidence, narrative, and the disclaimer (every surface)."""

    id: str
    run_id: str
    symbol: str
    trade_date: date
    side: str
    rank: int
    display_score: float
    confidence: float
    band: str
    evidence: Mapping[str, Any]
    narrative: NarrativeView | None
    entry_price: float | None
    entry_date: date | None
    disclaimer: str = field(default=DISCLAIMER)


def trigger_run(
    engine: Engine,
    config: ScoringConfig,
    *,
    trade_date: date,
    trigger: str = "api",
    queued_timeout_seconds: int = 600,
) -> TriggerResult:
    """Insert a `queued` run for the validated `trade_date` (API and MCP path, ADR-020).

    Stale queued rows are reaped first (`not_picked_up`) so a missing worker cannot block
    triggers forever. Another active run gives `already_running` (HTTP 409 `run-in-progress`).
    """
    try:
        with session_scope(engine) as session:
            reap(session, queued_timeout_seconds=queued_timeout_seconds, abandoned=False)
            digest = ensure_config_version(session, config)
            session.flush()
            run_id = insert_run(
                session,
                trade_date=trade_date,
                trigger=trigger,
                config_hash=digest,
                code_version=code_version(),
            )
    except IntegrityError:
        with session_scope(engine) as session:
            active = active_run(session)
        return TriggerResult(
            status="already_running",
            trade_date=trade_date,
            active_run_id=None if active is None else active[0],
            active_trade_date=None if active is None else active[1],
        )
    return TriggerResult(status="queued", trade_date=trade_date, run_id=run_id)


def run_next_queued(
    engine: Engine, deps: RunDeps, *, progress: Progress | None = None
) -> RunOutcome | None:
    """Claim and execute the oldest queued run (worker path); None when idle or locked out.

    Takes the run lock, reaps abandoned and stale queued runs, then claims with
    `FOR UPDATE SKIP LOCKED` and runs the same orchestrator as `execute_run`.
    """
    with run_lock(engine) as lock:
        if lock is None:
            return None
        with session_scope(engine) as session:
            reap(session, queued_timeout_seconds=deps.queued_timeout_seconds)
            row = session.execute(
                sa.select(Run.id, Run.trade_date, Run.config_hash)
                .where(Run.state == RunState.QUEUED.value)
                .order_by(Run.created_at, Run.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            ).first()
        if row is None:
            return None
        return drive_run(
            engine,
            deps,
            row.id,
            trade_date=row.trade_date,
            config_hash=row.config_hash,
            progress=progress,
        )


def _view(run: Run, transitions: tuple[TransitionView, ...] = ()) -> RunView:
    return RunView(
        id=run.id,
        trade_date=run.trade_date,
        state=run.state,
        trigger=run.trigger,
        config_hash=run.config_hash,
        code_version=run.code_version,
        market_regime=run.market_regime,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        published_at=run.published_at,
        superseded_by=run.superseded_by,
        error_code=run.error_code,
        error_detail=run.error_detail,
        summary=dict(run.summary or {}),
        transitions=transitions,
    )


def _transitions(session: Session, run_id: str) -> tuple[TransitionView, ...]:
    rows = session.scalars(
        sa.select(RunTransition).where(RunTransition.run_id == run_id).order_by(RunTransition.seq)
    )
    return tuple(
        TransitionView(
            seq=t.seq,
            from_state=t.from_state,
            to_state=t.to_state,
            at=t.at,
            detail=dict(t.detail or {}),
        )
        for t in rows
    )


def get_run(engine: Engine, run_id: str) -> RunView | None:
    """One run with its transition list (`GET /api/v1/runs/{id}`), or None."""
    with session_scope(engine) as session:
        run = session.get(Run, run_id)
        return None if run is None else _view(run, _transitions(session, run_id))


def list_runs(
    engine: Engine, *, limit: int = DEFAULT_LIST_LIMIT, before: str | None = None
) -> list[RunView]:
    """Runs newest first (ULID order); `before` is a run id cursor. Limit 1 to 200."""
    size = max(1, min(limit, MAX_LIST_LIMIT))
    stmt = sa.select(Run).order_by(Run.id.desc()).limit(size)
    if before is not None:
        stmt = stmt.where(Run.id < before)
    with session_scope(engine) as session:
        return [_view(r) for r in session.scalars(stmt)]


def _current() -> sa.ColumnElement[bool]:
    return sa.and_(Run.published_at.is_not(None), Run.superseded_by.is_(None))


def latest_published_run(engine: Engine) -> RunView | None:
    """The current published run with the greatest trade date, or None (read rule)."""
    with session_scope(engine) as session:
        run = session.scalars(
            sa.select(Run).where(_current()).order_by(Run.trade_date.desc()).limit(1)
        ).first()
        return None if run is None else _view(run, _transitions(session, run.id))


def published_run_for_date(engine: Engine, trade_date: date) -> RunView | None:
    """The current published run for `trade_date`, or None."""
    with session_scope(engine) as session:
        run = session.scalars(
            sa.select(Run).where(_current(), Run.trade_date == trade_date)
        ).first()
        return None if run is None else _view(run, _transitions(session, run.id))


def recommendations_for_run(engine: Engine, run_id: str) -> list[RecommendationView]:
    """The run's picks, buys then sells, each in rank order (empty unless published)."""
    with session_scope(engine) as session:
        rows = session.execute(
            sa.select(Recommendation, Narrative)
            .join(Run, Run.id == Recommendation.run_id)
            .outerjoin(Narrative, Narrative.recommendation_id == Recommendation.id)
            .where(Recommendation.run_id == run_id, Run.published_at.is_not(None))
            .order_by(Recommendation.side, Recommendation.rank)
        ).all()
        return [
            RecommendationView(
                id=rec.id,
                run_id=rec.run_id,
                symbol=rec.symbol,
                trade_date=rec.trade_date,
                side=rec.side,
                rank=rec.rank,
                display_score=float(rec.display_score),
                confidence=rec.confidence,
                band=rec.band,
                evidence=dict(rec.evidence),
                narrative=None
                if nar is None
                else NarrativeView(
                    text=nar.text,
                    source=nar.source,
                    model=nar.model,
                    prompt_version=nar.prompt_version,
                ),
                entry_price=rec.entry_price,
                entry_date=rec.entry_date,
            )
            for rec, nar in rows
        ]
