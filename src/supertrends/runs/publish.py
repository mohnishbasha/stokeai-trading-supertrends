# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Atomic publication of a run (FR-902, FR-903, ARCHITECTURE section 8.2, ADR-068).

One SERIALIZABLE transaction, retried up to three times on a serialization failure:

1. lock the run and assert it is `narrating`;
2. insert the recommendations (with evidence) and their narratives;
3. lock the current published run for the date, if any, and set its `superseded_by`;
4. move the run to `published` (`published_at`, `finished_at`, summary, transition row);
5. increment the counters; commit.

Readers see either the previous published run or the whole new one, never a mix.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import sqlalchemy as sa
from psycopg import errors as pg_errors
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from supertrends.data.models import Narrative, Recommendation, Run
from supertrends.runs.ids import new_ulid
from supertrends.runs.narrator import NarratedPick
from supertrends.runs.pipeline import display_decimal, json_safe
from supertrends.runs.repo import increment_counter, transition
from supertrends.runs.state import RunState
from supertrends.selection.ranking import Pick

__all__ = ["MAX_ATTEMPTS", "PublishError", "PublishItem", "publish"]

MAX_ATTEMPTS = 3
NARRATIVE_TOTAL = "supertrends_narrative_total"


class PublishError(RuntimeError):
    """The run cannot be published (wrong state, or retries exhausted)."""


@dataclass(frozen=True)
class PublishItem:
    """One pick and what the narrator produced for it."""

    pick: Pick
    narrated: NarratedPick


def _is_serialization_failure(exc: sa.exc.DBAPIError) -> bool:
    return isinstance(exc.orig, pg_errors.SerializationFailure | pg_errors.DeadlockDetected)


def _publish_once(
    session: Session,
    run_id: str,
    trade_date: date,
    items: Sequence[PublishItem],
    summary: Mapping[str, Any],
) -> None:
    state = session.scalar(sa.select(Run.state).where(Run.id == run_id).with_for_update())
    if state != RunState.NARRATING.value:
        msg = f"run {run_id} is {state}, expected narrating"
        raise PublishError(msg)
    for item in items:
        pick = item.pick
        rec_id = new_ulid()
        session.add(
            Recommendation(
                id=rec_id,
                run_id=run_id,
                symbol=pick.ticker,
                trade_date=trade_date,
                side=pick.side,
                rank=pick.rank,
                display_score=display_decimal(pick.display_score),
                confidence=pick.confidence,
                band=str(pick.band),
                evidence=json_safe(dict(item.narrated.evidence)),
            )
        )
        session.flush()
        text = item.narrated.narrative
        if text is not None:
            session.add(
                Narrative(
                    recommendation_id=rec_id,
                    text=text.text,
                    source=text.source,
                    model=text.model,
                    prompt_version=text.prompt_version,
                    tokens_in=text.tokens_in,
                    tokens_out=text.tokens_out,
                    attempts=text.attempts,
                    rejection_reasons=list(text.rejection_reasons),
                )
            )
            increment_counter(session, NARRATIVE_TOTAL, {"source": text.source, "result": "ok"})
    previous = session.scalar(
        sa.select(Run.id)
        .where(
            Run.trade_date == trade_date,
            Run.published_at.is_not(None),
            Run.superseded_by.is_(None),
            Run.id != run_id,
        )
        .with_for_update()
    )
    if previous is not None:
        session.execute(sa.update(Run).where(Run.id == previous).values(superseded_by=run_id))
    detail = {"supersedes": previous} if previous else {}
    transition(session, run_id, RunState.PUBLISHED, detail=detail, summary=summary)


def publish(
    engine: Engine,
    run_id: str,
    trade_date: date,
    items: Sequence[PublishItem],
    summary: Mapping[str, Any],
) -> None:
    """Publish the run in one SERIALIZABLE transaction; raise on failure (nothing visible)."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        conn = engine.connect().execution_options(isolation_level="SERIALIZABLE")
        try:
            with Session(bind=conn) as session, session.begin():
                _publish_once(session, run_id, trade_date, items, summary)
            return
        except sa.exc.DBAPIError as exc:
            if not _is_serialization_failure(exc) or attempt == MAX_ATTEMPTS:
                raise
        finally:
            conn.close()
    msg = f"run {run_id} was not published after {MAX_ATTEMPTS} attempts"  # pragma: no cover
    raise PublishError(msg)  # pragma: no cover
