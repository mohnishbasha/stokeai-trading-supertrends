# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Unit-test fixtures: a SQLite stand-in for the watchlist tables (no Postgres, no network).

The Postgres CHECK constraints (regex operators) and triggers are not portable, so the
fixture creates the watchlist tables without CHECK constraints. The service enforces those
rules itself; the Postgres behavior is covered by tests/integration.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from supertrends.data.models import (
    Base,
    Ticker,
    Watchlist,
    WatchlistGroup,
    WatchlistGroupMember,
    WatchlistItem,
)

WATCHLIST_TABLES = (Ticker, Watchlist, WatchlistItem, WatchlistGroup, WatchlistGroupMember)


@pytest.fixture
def watchlist_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'watchlist.db'}"


@pytest.fixture
def watchlist_engine(watchlist_url: str) -> Iterator[Engine]:
    engine = create_engine(watchlist_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _now(dbapi_connection: object, _record: object) -> None:
        dbapi_connection.create_function("now", 0, lambda: "2026-11-15 00:00:00")  # type: ignore[attr-defined]

    tables = [m.__table__ for m in WATCHLIST_TABLES]
    saved = {t: set(t.constraints) for t in tables}
    for table in tables:
        for constraint in [c for c in table.constraints if isinstance(c, CheckConstraint)]:
            table.constraints.discard(constraint)
    try:
        Base.metadata.create_all(engine, tables=tables)
    finally:
        for table, constraints in saved.items():
            table.constraints.update(constraints)
    yield engine
    engine.dispose()


@pytest.fixture
def watchlist_session(watchlist_engine: Engine) -> Iterator[Session]:
    with sessionmaker(bind=watchlist_engine, expire_on_commit=False)() as session:
        yield session
