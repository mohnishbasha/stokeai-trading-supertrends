# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Database operations of a run: lock, reaping, inserts, transitions, counters (ADR-021, ADR-023).

Every state change goes through `transition`, which locks the row, validates the edge, updates
`runs`, inserts the next `run_transitions` row, and increments
`supertrends_run_state_total{state}`, all in the caller's transaction (ARCHITECTURE section 8.1).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Connection, Engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from supertrends.data.models import (
    ConfigVersion,
    MetricCounter,
    Run,
    RunTransition,
    Ticker,
    WatchlistItem,
)
from supertrends.runs.ids import new_ulid
from supertrends.runs.state import TERMINAL, ErrorCode, RunState, check_transition
from supertrends.scoring.config import ScoringConfig, config_hash

__all__ = [
    "LOCK_KEY",
    "RUN_STATE_TOTAL",
    "active_run",
    "ensure_config_version",
    "increment_counter",
    "insert_run",
    "reap",
    "run_lock",
    "scored_watchlist_symbols",
    "transition",
]

LOCK_KEY = "supertrends.run"
RUN_STATE_TOTAL = "supertrends_run_state_total"
ACTIVE_STATES = tuple(s.value for s in RunState if s not in TERMINAL)


@contextmanager
def run_lock(engine: Engine) -> Iterator[Connection | None]:
    """Hold the session-level run advisory lock for the duration of the block (ADR-021).

    Yields the connection that holds the lock, or None when another process holds it. The lock
    is released on exit; if the release fails the connection is discarded so the lock cannot
    leak into the pool.
    """
    conn = engine.connect()
    held = False
    try:
        held = bool(
            conn.scalar(sa.select(sa.func.pg_try_advisory_lock(sa.func.hashtext(LOCK_KEY))))
        )
        conn.commit()
        yield conn if held else None
    finally:
        if held:
            try:
                conn.scalar(sa.select(sa.func.pg_advisory_unlock(sa.func.hashtext(LOCK_KEY))))
                conn.commit()
            except sa.exc.SQLAlchemyError:
                conn.invalidate()
        conn.close()


def increment_counter(
    session: Session, name: str, labels: Mapping[str, str], by: float = 1.0
) -> None:
    """Add `by` to the persisted counter `name{labels}` (ADR-023)."""
    stmt = insert(MetricCounter).values(name=name, labels=dict(labels), value=by)
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=["name", "labels"],
            set_={"value": MetricCounter.value + stmt.excluded.value, "updated_at": sa.func.now()},
        )
    )


def ensure_config_version(session: Session, cfg: ScoringConfig) -> str:
    """Store the config document under its hash if new; return the hash."""
    digest = config_hash(cfg)
    session.execute(
        insert(ConfigVersion)
        .values(hash=digest, version=cfg.scoring.version, document=cfg.model_dump(mode="json"))
        .on_conflict_do_nothing(index_elements=["hash"])
    )
    return digest


def insert_run(
    session: Session,
    *,
    trade_date: date,
    trigger: str,
    config_hash: str,
    code_version: str,
) -> str:
    """Insert a `queued` run and its first transition; return the new id.

    Raises IntegrityError when another run is active (`ux_runs_one_active`).
    """
    run_id = new_ulid()
    session.add(
        Run(
            id=run_id,
            trade_date=trade_date,
            state=RunState.QUEUED.value,
            trigger=trigger,
            config_hash=config_hash,
            code_version=code_version,
        )
    )
    session.flush()
    session.add(RunTransition(run_id=run_id, seq=1, from_state=None, to_state=RunState.QUEUED))
    increment_counter(session, RUN_STATE_TOTAL, {"state": RunState.QUEUED.value})
    session.flush()
    return run_id


def transition(  # noqa: PLR0913 - keyword-only columns of the update
    session: Session,
    run_id: str,
    to_state: RunState,
    *,
    detail: Mapping[str, Any] | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
    summary: Mapping[str, Any] | None = None,
) -> RunState:
    """Move the run to `to_state` in the caller's transaction; return the previous state.

    Raises IllegalTransitionError for an edge the state machine does not allow and LookupError
    for an unknown run.
    """
    current = session.scalar(sa.select(Run.state).where(Run.id == run_id).with_for_update())
    if current is None:
        msg = f"run {run_id} does not exist"
        raise LookupError(msg)
    source = RunState(current)
    target = check_transition(source, to_state)
    now = sa.func.now()
    values: dict[str, Any] = {"state": target.value}
    if source == RunState.QUEUED:
        values["started_at"] = sa.func.coalesce(Run.started_at, now)
    if target in TERMINAL:
        values["finished_at"] = now
    if target == RunState.PUBLISHED:
        values["published_at"] = now
    if error_code is not None:
        values["error_code"] = error_code
        values["error_detail"] = error_detail
    if summary is not None:
        values["summary"] = dict(summary)
    session.execute(sa.update(Run).where(Run.id == run_id).values(**values))
    seq = session.scalar(
        sa.select(sa.func.coalesce(sa.func.max(RunTransition.seq), 0)).where(
            RunTransition.run_id == run_id
        )
    )
    session.add(
        RunTransition(
            run_id=run_id,
            seq=int(seq or 0) + 1,
            from_state=source.value,
            to_state=target.value,
            detail=dict(detail or {}),
        )
    )
    increment_counter(session, RUN_STATE_TOTAL, {"state": target.value})
    session.flush()
    return source


def reap(
    session: Session,
    *,
    queued_timeout_seconds: int,
    abandoned: bool = True,
    now: datetime | None = None,
) -> list[tuple[str, str]]:
    """Fail runs no process can be executing (ADR-021); return `(run_id, error_code)` pairs.

    With `abandoned` (only while holding the run lock): every non-terminal, non-queued run
    becomes `failed` with `abandoned`. Always: queued runs older than the timeout become
    `failed` with `not_picked_up`.
    """
    reaped: list[tuple[str, str]] = []
    if abandoned:
        ids = session.scalars(
            sa.select(Run.id)
            .where(Run.state.in_([s for s in ACTIVE_STATES if s != RunState.QUEUED]))
            .order_by(Run.id)
        ).all()
        for run_id in ids:
            transition(
                session,
                run_id,
                RunState.FAILED,
                detail={"reason": ErrorCode.ABANDONED.value},
                error_code=ErrorCode.ABANDONED,
                error_detail="no live process held the run lock",
            )
            reaped.append((run_id, ErrorCode.ABANDONED.value))
    cutoff = (now or datetime.now(UTC)) - timedelta(seconds=queued_timeout_seconds)
    stale = session.scalars(
        sa.select(Run.id)
        .where(Run.state == RunState.QUEUED.value, Run.created_at < cutoff)
        .order_by(Run.id)
    ).all()
    for run_id in stale:
        transition(
            session,
            run_id,
            RunState.FAILED,
            detail={"reason": ErrorCode.NOT_PICKED_UP.value},
            error_code=ErrorCode.NOT_PICKED_UP,
            error_detail=f"queued longer than {queued_timeout_seconds} s",
        )
        reaped.append((run_id, ErrorCode.NOT_PICKED_UP.value))
    return reaped


def active_run(session: Session) -> tuple[str, date] | None:
    """The non-terminal run (there is at most one), as `(id, trade_date)`."""
    row = session.execute(
        sa.select(Run.id, Run.trade_date).where(Run.state.in_(ACTIVE_STATES)).limit(1)
    ).first()
    return None if row is None else (row.id, row.trade_date)


def scored_watchlist_symbols(session: Session) -> list[str]:
    """Watchlist symbols the run scores: `scored`, resolved, not crypto and not an index."""
    rows = session.scalars(
        sa.select(WatchlistItem.symbol)
        .join(Ticker, Ticker.symbol == WatchlistItem.symbol)
        .where(
            WatchlistItem.scored.is_(True),
            Ticker.resolution == "resolved",
            Ticker.type.not_in(("crypto", "index")),
        )
    )
    return sorted(set(rows))
