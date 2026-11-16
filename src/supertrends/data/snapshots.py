# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Persistence of indicator snapshots (S2-T09, ARCHITECTURE sections 4 and 5).

`indicator_snapshots` has one row per (run, symbol). The trade date and the config hash live on
the `runs` row (FK `config_versions`); the document repeats them (`as_of`, `config_hash`) so it
is self-describing. The table is append-only (trigger), so the write is insert-only:

* no row yet: insert (`stored`);
* a row exists with an equal document: do nothing (`unchanged`), which makes a retry of the
  `computing` step safe;
* a row exists with a different document: `SnapshotConflictError`. A recompute with different
  bars or a different config is a new run, never an update.

`compute_and_store` is the whole `computing` step for a list of symbols: load stored bars up to
the run's trade date, compute, write. The run orchestrator (Sprint 3) calls it.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from supertrends.data.models import BarDaily, BarIntraday, IndicatorSnapshot, Run
from supertrends.indicators.registry import Bundle
from supertrends.scoring.config import ScoringConfig, config_hash
from supertrends.scoring.snapshot import compute_snapshot

__all__ = [
    "SnapshotConflictError",
    "SnapshotSummary",
    "compute_and_store",
    "load_bundle",
    "read_snapshot",
    "write_snapshot",
]

_NY = ZoneInfo("America/New_York")
STORED = "stored"
UNCHANGED = "unchanged"


class SnapshotConflictError(Exception):
    """A different snapshot already exists for the run and symbol."""


@dataclass
class SnapshotSummary:
    """Outcome of `compute_and_store`: symbols written, already present, and skipped (reason)."""

    stored: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)


def write_snapshot(session: Session, run_id: str, symbol: str, doc: dict[str, Any]) -> str:
    """Insert the snapshot; `stored`, or `unchanged` when an equal one exists.

    Raises SnapshotConflictError when a different document exists for the run and symbol.
    Race-safe: the insert is ON CONFLICT DO NOTHING and the existing row is read afterwards.
    """
    inserted = session.execute(
        insert(IndicatorSnapshot)
        .values(run_id=run_id, symbol=symbol, values=doc)
        .on_conflict_do_nothing(index_elements=["run_id", "symbol"])
        .returning(IndicatorSnapshot.symbol)
    ).first()
    if inserted is not None:
        return STORED
    if read_snapshot(session, run_id, symbol) == doc:
        return UNCHANGED
    msg = f"a different indicator snapshot already exists for run {run_id} and symbol {symbol}"
    raise SnapshotConflictError(msg)


def read_snapshot(session: Session, run_id: str, symbol: str) -> dict[str, Any] | None:
    """The stored document, or None."""
    return session.scalar(
        sa.select(IndicatorSnapshot.values).where(
            IndicatorSnapshot.run_id == run_id, IndicatorSnapshot.symbol == symbol
        )
    )


def load_bundle(session: Session, symbol: str, as_of: dt.date) -> Bundle | None:
    """Stored daily bars up to `as_of` and the 5-minute bars of those sessions, as arrays.

    Returns None when the symbol has no daily bars on or before `as_of`. Intraday starts are
    session-local (New York) wall-clock minutes, as the flow estimator expects.
    """
    daily = session.execute(
        sa.select(
            BarDaily.date,
            BarDaily.open,
            BarDaily.high,
            BarDaily.low,
            BarDaily.close,
            BarDaily.volume,
        )
        .where(BarDaily.symbol == symbol, BarDaily.date <= as_of)
        .order_by(BarDaily.date)
    ).all()
    if not daily:
        return None
    day_index = {row.date: i for i, row in enumerate(daily)}
    # the UTC window is wider than the sessions; the loop keeps bars of known sessions only
    limit = dt.datetime.combine(as_of + dt.timedelta(days=2), dt.time(), tzinfo=dt.UTC)
    first = dt.datetime.combine(daily[0].date - dt.timedelta(days=1), dt.time(), tzinfo=dt.UTC)
    rows = session.execute(
        sa.select(
            BarIntraday.ts,
            BarIntraday.high,
            BarIntraday.low,
            BarIntraday.close,
            BarIntraday.volume,
        )
        .where(BarIntraday.symbol == symbol, BarIntraday.ts >= first, BarIntraday.ts < limit)
        .order_by(BarIntraday.ts)
    ).all()
    local = [
        (r, (r.ts if r.ts.tzinfo else r.ts.replace(tzinfo=dt.UTC)).astimezone(_NY)) for r in rows
    ]
    kept = [(r, t.replace(tzinfo=None)) for r, t in local if t.date() in day_index]
    return Bundle(
        dates=np.array([r.date for r in daily], dtype="datetime64[D]"),
        open=np.array([r.open for r in daily], dtype=np.float64),
        high=np.array([r.high for r in daily], dtype=np.float64),
        low=np.array([r.low for r in daily], dtype=np.float64),
        close=np.array([r.close for r in daily], dtype=np.float64),
        volume=np.array([float(r.volume) for r in daily], dtype=np.float64),
        i_day=np.array([day_index[t.date()] for _, t in kept], dtype=np.int64),
        bar_start=np.array([t for _, t in kept], dtype="datetime64[m]"),
        i_high=np.array([r.high for r, _ in kept], dtype=np.float64),
        i_low=np.array([r.low for r, _ in kept], dtype=np.float64),
        i_close=np.array([r.close for r, _ in kept], dtype=np.float64),
        i_volume=np.array([float(r.volume) for r, _ in kept], dtype=np.float64),
    )


def compute_and_store(
    session: Session, run_id: str, symbols: Sequence[str], cfg: ScoringConfig, as_of: dt.date
) -> SnapshotSummary:
    """Compute and write the snapshot of every symbol that has bars up to `as_of`.

    Symbols without bars are skipped with reason `no_data`. Raises ValueError when the run does
    not exist or its `config_hash` is not the hash of `cfg` (the snapshot would be filed under
    the wrong config). The caller owns the transaction.
    """
    stored_hash = session.scalar(sa.select(Run.config_hash).where(Run.id == run_id))
    if stored_hash is None:
        msg = f"run {run_id} does not exist"
        raise ValueError(msg)
    if stored_hash != config_hash(cfg):
        msg = f"config hash of run {run_id} ({stored_hash}) is not the hash of the given config"
        raise ValueError(msg)
    summary = SnapshotSummary()
    for symbol in symbols:
        bundle = load_bundle(session, symbol, as_of)
        if bundle is None:
            summary.skipped[symbol] = "no_data"
            continue
        outcome = write_snapshot(session, run_id, symbol, compute_snapshot(bundle, cfg, as_of))
        (summary.stored if outcome == STORED else summary.unchanged).append(symbol)
    return summary
