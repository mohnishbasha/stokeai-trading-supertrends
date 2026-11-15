# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Schema, migrations, and append-only triggers against real Postgres (ARCHITECTURE 5.1-5.4).

Runs only when SUPERTRENDS_IT_DATABASE_URL is set (the CI integration-tests job). Every test
starts from an empty database: the fixture downgrades to base, then upgrades to head.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from supertrends.data import db
from supertrends.data.models import APPEND_ONLY_TABLES, Base

URL = os.environ.get("SUPERTRENDS_IT_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="set SUPERTRENDS_IT_DATABASE_URL to run")

HASH = "sha256:" + "a" * 64
RUN_ID = "0" * 25 + "1"
RUN_ID_2 = "0" * 25 + "2"
REC_ID = "0" * 25 + "3"


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
    yield eng
    _downgrade_base(eng)
    eng.dispose()


def _exec(connection: Connection, sql: str, **params: object) -> None:
    connection.execute(text(sql), params)


def _seed_run(connection: Connection, run_id: str = RUN_ID, state: str = "queued") -> None:
    _exec(
        connection,
        "INSERT INTO config_versions (hash, version, document) VALUES (:h, 1, '{}') "
        "ON CONFLICT DO NOTHING",
        h=HASH,
    )
    published = "now()" if state == "published" else "NULL"
    _exec(
        connection,
        "INSERT INTO runs (id, trade_date, state, trigger, config_hash, code_version, "
        "published_at) "
        f"VALUES (:id, '2026-11-13', :state, 'cli', :h, 'test', {published})",
        id=run_id,
        state=state,
        h=HASH,
    )


def _seed_recommendation(connection: Connection) -> None:
    _seed_run(connection, state="published")
    _exec(connection, "INSERT INTO tickers (symbol) VALUES ('AAPL')")
    _exec(
        connection,
        "INSERT INTO recommendations (id, run_id, symbol, trade_date, side, rank, display_score, "
        "confidence, band, evidence) VALUES (:id, :run, 'AAPL', '2026-11-13', 'buy', 1, 80.5, "
        "70, 'strong_buy', '{}')",
        id=REC_ID,
        run=RUN_ID,
    )


def _seed_factor_score(connection: Connection) -> None:
    _seed_run(connection)
    _exec(connection, "INSERT INTO tickers (symbol) VALUES ('AAPL')")
    _exec(
        connection,
        "INSERT INTO ticker_scores (run_id, symbol, status, data_quality) "
        "VALUES (:run, 'AAPL', 'scored', 'ok')",
        run=RUN_ID,
    )
    _exec(
        connection,
        "INSERT INTO factor_scores (run_id, symbol, factor_id, score, weight, contribution, "
        "quality, evidence) VALUES (:run, 'AAPL', 'trend', 50, 10, 5, 'ok', '{}')",
        run=RUN_ID,
    )


def _assert_append_only(connection: Connection, sql: str, table: str) -> None:
    with pytest.raises(DBAPIError) as caught:
        connection.execute(text(sql))
    assert getattr(caught.value.orig, "sqlstate", None) == "P0001"
    assert "append_only_violation" in str(caught.value.orig)
    assert table in str(caught.value.orig)


def test_it_schema_migrations_upgrade_head_and_downgrade_base_succeed(engine: Engine) -> None:
    assert db.migrations_at_head(engine)
    _downgrade_base(engine)
    with engine.connect() as connection:
        leftovers = connection.execute(
            text(
                "SELECT table_schema || '.' || table_name FROM information_schema.tables "
                "WHERE table_schema IN ('public', 'backtests') AND table_name <> 'alembic_version'"
            )
        ).all()
        functions = connection.execute(
            text("SELECT proname FROM pg_proc WHERE proname LIKE 'supertrends\\_%'")
        ).all()
        schema = connection.execute(
            text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'backtests'")
        ).all()
    assert leftovers == []
    assert functions == []
    assert schema == []
    db.migrate(engine)
    assert db.migrations_at_head(engine)


def test_it_schema_models_match_migrated_database(engine: Engine) -> None:
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"include_schemas": True, "compare_type": True}
        )
        diff = compare_metadata(context, Base.metadata)
    assert diff == []


def test_it_schema_migrations_at_head_false_when_behind_and_true_after_migrate(
    engine: Engine,
) -> None:
    config = db.alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0001")
    assert db.database_revision(engine) == "0001"
    assert not db.migrations_at_head(engine)
    assert db.migrate(engine) == db.head_revision()
    assert db.migrations_at_head(engine)


def test_it_schema_migrate_is_idempotent_at_head(engine: Engine) -> None:
    assert db.migrate(engine) == db.head_revision()


def test_it_schema_session_scope_roundtrip(engine: Engine) -> None:
    with db.session_scope(engine) as session:
        session.execute(text("INSERT INTO tickers (symbol, name) VALUES ('MSFT', 'Microsoft')"))
    with db.session_scope(engine) as session:
        name = session.execute(text("SELECT name FROM tickers WHERE symbol = 'MSFT'")).scalar_one()
    assert name == "Microsoft"


def test_it_schema_bars_composite_primary_key_rejects_duplicate_ticker_ts(engine: Engine) -> None:
    bar = (
        "INSERT INTO {table} (symbol, {key}, open, high, low, close, volume, provider) "
        "VALUES ('AAPL', {value}, 1, 2, 1, 2, 10, 'fixture')"
    )
    with engine.begin() as connection:
        _exec(connection, "INSERT INTO tickers (symbol) VALUES ('AAPL')")
        connection.execute(text(bar.format(table="bars_daily", key="date", value="'2026-11-13'")))
        connection.execute(
            text(bar.format(table="bars_intraday", key="ts", value="'2026-11-13T14:30:00Z'"))
        )
    for table, key, value in (
        ("bars_daily", "date", "'2026-11-13'"),
        ("bars_intraday", "ts", "'2026-11-13T14:30:00Z'"),
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text(bar.format(table=table, key=key, value=value)))


def test_it_schema_bars_daily_rejects_high_below_low(engine: Engine) -> None:
    with engine.begin() as connection:
        _exec(connection, "INSERT INTO tickers (symbol) VALUES ('AAPL')")
    with pytest.raises(IntegrityError), engine.begin() as connection:
        _exec(
            connection,
            "INSERT INTO bars_daily (symbol, date, open, high, low, close, volume, provider) "
            "VALUES ('AAPL', '2026-11-13', 1, 1, 2, 1, 1, 'fixture')",
        )


def test_it_schema_recommendations_update_rejected_by_append_only_trigger(
    engine: Engine,
) -> None:
    with engine.begin() as connection:
        _seed_recommendation(connection)
    with engine.connect() as connection:
        _assert_append_only(
            connection,
            f"UPDATE recommendations SET band = 'buy' WHERE id = '{REC_ID}'",
            "recommendations",
        )


def test_it_schema_recommendations_delete_rejected_by_append_only_trigger(
    engine: Engine,
) -> None:
    with engine.begin() as connection:
        _seed_recommendation(connection)
    with engine.connect() as connection:
        _assert_append_only(
            connection, f"DELETE FROM recommendations WHERE id = '{REC_ID}'", "recommendations"
        )


def test_it_schema_recommendations_entry_price_settable_once_from_null(engine: Engine) -> None:
    with engine.begin() as connection:
        _seed_recommendation(connection)
    with engine.begin() as connection:
        _exec(
            connection,
            "UPDATE recommendations SET entry_price = 190.5, entry_date = '2026-11-16' "
            "WHERE id = :id",
            id=REC_ID,
        )
    with engine.connect() as connection:
        _assert_append_only(
            connection,
            f"UPDATE recommendations SET entry_price = 191 WHERE id = '{REC_ID}'",
            "recommendations",
        )


def test_it_schema_factor_scores_delete_rejected_by_append_only_trigger(engine: Engine) -> None:
    with engine.begin() as connection:
        _seed_factor_score(connection)
    with engine.connect() as connection:
        _assert_append_only(connection, "DELETE FROM factor_scores", "factor_scores")


def test_it_schema_factor_scores_update_rejected_by_append_only_trigger(engine: Engine) -> None:
    with engine.begin() as connection:
        _seed_factor_score(connection)
    with engine.connect() as connection:
        _assert_append_only(connection, "UPDATE factor_scores SET weight = 1", "factor_scores")


def test_it_schema_every_append_only_table_has_the_reject_trigger(engine: Engine) -> None:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT c.relname, p.proname FROM pg_trigger t "
                "JOIN pg_class c ON c.oid = t.tgrelid "
                "JOIN pg_proc p ON p.oid = t.tgfoid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE NOT t.tgisinternal AND n.nspname = 'public'"
            )
        ).all()
    attached = {(relname, proname) for relname, proname in rows}
    for table in APPEND_ONLY_TABLES:
        assert (table, "supertrends_reject_mutation") in attached
    assert ("recommendations", "supertrends_recommendations_guard") in attached
    assert ("runs", "supertrends_runs_guard") in attached


def test_it_schema_runs_forward_transition_allowed_and_backward_rejected(engine: Engine) -> None:
    with engine.begin() as connection:
        _seed_run(connection)
        _exec(connection, "UPDATE runs SET state = 'ingesting' WHERE id = :id", id=RUN_ID)
        _exec(connection, "UPDATE runs SET state = 'computing' WHERE id = :id", id=RUN_ID)
    with engine.connect() as connection:
        _assert_append_only(
            connection,
            f"UPDATE runs SET state = 'ingesting' WHERE id = '{RUN_ID}'",
            "runs",
        )
    with engine.connect() as connection:
        _assert_append_only(
            connection,
            f"UPDATE runs SET state = 'published' WHERE id = '{RUN_ID}'",
            "runs",
        )


def test_it_schema_runs_terminal_immutable_except_superseded_by_set_once(engine: Engine) -> None:
    with engine.begin() as connection:
        _seed_run(connection, state="published")
    with engine.connect() as connection:
        _assert_append_only(
            connection,
            f"UPDATE runs SET code_version = 'x' WHERE id = '{RUN_ID}'",
            "runs",
        )
    with engine.begin() as connection:
        _exec(
            connection,
            "INSERT INTO runs (id, trade_date, state, trigger, config_hash, code_version, "
            "published_at) VALUES (:id, '2026-11-14', 'published', 'cli', :h, 'test', now())",
            id=RUN_ID_2,
            h=HASH,
        )
        _exec(
            connection, "UPDATE runs SET superseded_by = :n WHERE id = :id", n=RUN_ID_2, id=RUN_ID
        )
    with engine.connect() as connection:
        _assert_append_only(
            connection,
            f"UPDATE runs SET superseded_by = NULL WHERE id = '{RUN_ID}'",
            "runs",
        )


def test_it_schema_runs_delete_rejected(engine: Engine) -> None:
    with engine.begin() as connection:
        _seed_run(connection)
    with engine.connect() as connection:
        _assert_append_only(connection, "DELETE FROM runs", "runs")


def test_it_schema_runs_only_one_active_run_at_a_time(engine: Engine) -> None:
    with engine.begin() as connection:
        _seed_run(connection)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        _exec(
            connection,
            "INSERT INTO runs (id, trade_date, trigger, config_hash, code_version) "
            "VALUES (:id, '2026-11-14', 'cli', :h, 'test')",
            id=RUN_ID_2,
            h=HASH,
        )


def test_it_schema_watchlist_cap_rejects_301st_item_at_commit(engine: Engine) -> None:
    with engine.begin() as connection:
        _exec(connection, "INSERT INTO watchlists (name) VALUES ('default')")
        _exec(
            connection,
            "INSERT INTO tickers (symbol) SELECT 'T' || g FROM generate_series(1, 301) g",
        )
        _exec(
            connection,
            "INSERT INTO watchlist_items (watchlist_id, symbol) "
            "SELECT 1, 'T' || g FROM generate_series(1, 300) g",
        )
    with pytest.raises(DBAPIError) as caught, engine.begin() as connection:
        _exec(connection, "INSERT INTO watchlist_items (watchlist_id, symbol) VALUES (1, 'T301')")
    assert getattr(caught.value.orig, "sqlstate", None) == "23514"


def test_it_schema_symbol_in_three_groups_is_stored_once(engine: Engine) -> None:
    with engine.begin() as connection:
        _exec(connection, "INSERT INTO watchlists (name) VALUES ('default')")
        _exec(connection, "INSERT INTO tickers (symbol) VALUES ('NVDA')")
        _exec(connection, "INSERT INTO watchlist_items (watchlist_id, symbol) VALUES (1, 'NVDA')")
        for slug in ("ai", "semis", "mega"):
            _exec(
                connection,
                "INSERT INTO watchlist_groups (watchlist_id, slug, name) VALUES (1, :s, :s)",
                s=slug,
            )
        _exec(
            connection,
            "INSERT INTO watchlist_group_members (group_id, watchlist_id, symbol) "
            "SELECT id, 1, 'NVDA' FROM watchlist_groups",
        )
    with engine.connect() as connection:
        items = connection.execute(text("SELECT count(*) FROM watchlist_items")).scalar_one()
        members = connection.execute(
            text("SELECT count(*) FROM watchlist_group_members")
        ).scalar_one()
    assert (items, members) == (1, 3)
