# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Indicator snapshot persistence against real Postgres (TS-IND-095, 256 to 259; S2-T09).

Runs only when SUPERTRENDS_IT_DATABASE_URL is set. Every test starts from an empty database.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from supertrends.data import db
from supertrends.data.ingest import ingest
from supertrends.data.models import ConfigVersion, Run
from supertrends.data.providers.fixture import FixtureFundamentals, FixtureProvider, FixtureUniverse
from supertrends.data.snapshots import (
    SnapshotConflictError,
    compute_and_store,
    read_snapshot,
    write_snapshot,
)
from supertrends.scoring.config import ScoringConfig, config_hash, load_scoring_config
from supertrends.scoring.snapshot import snapshot_bytes

URL = os.environ.get("SUPERTRENDS_IT_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="set SUPERTRENDS_IT_DATABASE_URL to run")

SEED = 20261114
END = date(2026, 11, 13)
SYMBOLS = ["FXA", "FXB", "FXE"]
RUN_A = "01JA0000000000000000000001"
RUN_B = "01JA0000000000000000000002"
CONFIG = Path(__file__).parents[2] / "config" / "scoring.yaml"


def _downgrade_base(engine: Engine) -> None:
    config = db.alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = db.create_db_engine(url=URL)
    _downgrade_base(eng)
    db.migrate(eng)
    universe = FixtureUniverse(seed=SEED, end_date=END)
    ingest(eng, FixtureProvider(universe), FixtureFundamentals(universe), SYMBOLS, as_of=END)
    yield eng
    _downgrade_base(eng)
    eng.dispose()


@pytest.fixture(scope="module")
def cfg() -> ScoringConfig:
    return load_scoring_config(CONFIG)


def _add_run(session: Session, run_id: str, cfg: ScoringConfig) -> None:
    digest = config_hash(cfg)
    if session.get(ConfigVersion, digest) is None:
        session.add(
            ConfigVersion(
                hash=digest, version=cfg.scoring.version, document=cfg.model_dump(mode="json")
            )
        )
        session.flush()
    session.add(
        Run(
            id=run_id,
            trade_date=END,
            state="computing",
            trigger="cli",
            config_hash=digest,
            code_version="test",
        )
    )
    session.flush()


def test_it_snapshots_persist_roundtrip_identical_json_for_same_inputs(
    engine: Engine, cfg: ScoringConfig
) -> None:
    """TS-IND-095: the fixture dataset round-trips and a recompute gives an identical document."""
    with Session(engine) as session, session.begin():
        _add_run(session, RUN_A, cfg)
        first = compute_and_store(session, RUN_A, SYMBOLS, cfg, END)
    assert first.stored == SYMBOLS
    assert first.skipped == {}
    with Session(engine) as session:
        stored = {s: read_snapshot(session, RUN_A, s) for s in SYMBOLS}
        symbols = session.execute(
            text("SELECT symbol FROM indicator_snapshots ORDER BY symbol")
        ).scalars()
        assert list(symbols) == SYMBOLS
    for doc in stored.values():
        assert doc is not None
        assert doc["config_hash"] == config_hash(cfg)
        assert doc["as_of"] == END.isoformat()
        assert doc["flow"]["quality"] == "intraday"
        assert doc["daily"]["sma_200"] is not None
    # recompute into a second run: the documents are identical to the stored ones
    with Session(engine) as session, session.begin():
        _add_run(session, RUN_B, cfg)
        compute_and_store(session, RUN_B, SYMBOLS, cfg, END)
    with Session(engine) as session:
        for symbol in SYMBOLS:
            a, b = read_snapshot(session, RUN_A, symbol), read_snapshot(session, RUN_B, symbol)
            assert a is not None
            assert b is not None
            assert snapshot_bytes(a) == snapshot_bytes(b)


def test_it_snapshots_write_same_document_twice_is_skipped(
    engine: Engine, cfg: ScoringConfig
) -> None:
    """TS-IND-256: writing an identical snapshot again leaves one row and reports unchanged."""
    doc = {"schema": 1, "daily": {"rsi": 55.5, "sma_200": None}}
    with Session(engine) as session, session.begin():
        _add_run(session, RUN_A, cfg)
        assert write_snapshot(session, RUN_A, "FXA", doc) == "stored"
        assert write_snapshot(session, RUN_A, "FXA", doc) == "unchanged"
    with Session(engine) as session:
        assert session.execute(text("SELECT count(*) FROM indicator_snapshots")).scalar() == 1
        assert read_snapshot(session, RUN_A, "FXA") == doc


def test_it_snapshots_write_different_document_for_same_key_raises(
    engine: Engine, cfg: ScoringConfig
) -> None:
    """TS-IND-257: a different document for the same run and symbol is a conflict, not an update."""
    with Session(engine) as session, session.begin():
        _add_run(session, RUN_A, cfg)
        write_snapshot(session, RUN_A, "FXA", {"schema": 1, "daily": {"rsi": 55.5}})
        with pytest.raises(SnapshotConflictError, match="FXA"):
            write_snapshot(session, RUN_A, "FXA", {"schema": 1, "daily": {"rsi": 56.0}})
    with Session(engine) as session:
        assert read_snapshot(session, RUN_A, "FXA") == {"schema": 1, "daily": {"rsi": 55.5}}
        assert read_snapshot(session, RUN_A, "FXB") is None


def test_it_snapshots_update_and_delete_rejected_by_append_only_trigger(
    engine: Engine, cfg: ScoringConfig
) -> None:
    """TS-IND-258: the table stays append-only; snapshot code never needs UPDATE or DELETE."""
    with Session(engine) as session, session.begin():
        _add_run(session, RUN_A, cfg)
        write_snapshot(session, RUN_A, "FXA", {"schema": 1})
    for sql in (
        "UPDATE indicator_snapshots SET values = '{}'::jsonb",
        "DELETE FROM indicator_snapshots",
    ):
        with engine.connect() as conn, pytest.raises(DBAPIError) as caught:
            conn.execute(text(sql))
        assert "append_only_violation" in str(caught.value.orig)


def test_it_snapshots_compute_and_store_skips_unknown_symbols_and_checks_config_hash(
    engine: Engine, cfg: ScoringConfig
) -> None:
    """TS-IND-259: symbols without bars are skipped with a reason; a config mismatch is refused."""
    with Session(engine) as session, session.begin():
        _add_run(session, RUN_A, cfg)
        summary = compute_and_store(session, RUN_A, ["FXA", "FXZ"], cfg, END)
    assert summary.stored == ["FXA"]
    assert summary.skipped == {"FXZ": "no_data"}
    other = cfg.model_copy(update={"min_history_bars": cfg.min_history_bars + 1})
    with Session(engine) as session, session.begin(), pytest.raises(ValueError, match="config"):
        compute_and_store(session, RUN_A, ["FXB"], other, END)
