# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Engine, session, and migration helpers (SQLite stands in; no network or Postgres)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Engine, create_engine, text

from supertrends.data import db
from supertrends.errors import ConfigError
from supertrends.settings import Settings


@pytest.fixture
def engine() -> Engine:
    return create_engine("sqlite://")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgresql://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"),
        ("postgres://u:p@h/d", "postgresql+psycopg://u:p@h/d"),
        ("postgresql+psycopg://u:p@h/d", "postgresql+psycopg://u:p@h/d"),
        ("sqlite://", "sqlite://"),
    ],
)
def test_unit_db_normalize_database_url_selects_psycopg_driver(raw: str, expected: str) -> None:
    assert db.normalize_database_url(raw) == expected


def test_unit_db_create_engine_reads_settings_database_url() -> None:
    settings = Settings(database_url="postgresql://u:secret@dbhost:5432/d")  # type: ignore[arg-type]
    engine = db.create_db_engine(settings)
    assert engine.url.host == "dbhost"
    assert engine.url.drivername == "postgresql+psycopg"


def test_unit_db_create_engine_explicit_url_wins() -> None:
    assert db.create_db_engine(url="sqlite://").url.drivername == "sqlite"


def test_unit_db_get_engine_uses_environment_and_reset_clears_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERTRENDS_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("SUPERTRENDS_ENV", "ci")
    db.reset_engine()
    first = db.get_engine()
    assert first is db.get_engine()
    db.reset_engine()
    assert db.get_engine() is not first
    db.reset_engine()


def test_unit_db_session_scope_commits_on_success(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (v integer)"))
    with db.session_scope(engine) as session:
        session.execute(text("INSERT INTO t VALUES (1)"))
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM t")).scalar_one() == 1


def test_unit_db_session_scope_rolls_back_on_error(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (v integer)"))

    def failing_write() -> None:
        with db.session_scope(engine) as session:
            session.execute(text("INSERT INTO t VALUES (1)"))
            raise RuntimeError

    with pytest.raises(RuntimeError):
        failing_write()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM t")).scalar_one() == 0


def test_unit_db_session_scope_defaults_to_process_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "get_engine", lambda: create_engine("sqlite://"))
    with db.session_scope() as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1


def test_unit_db_head_revision_is_latest_bundled_revision() -> None:
    head = db.head_revision()
    names = sorted(p.name for p in (db.migrations_dir() / "versions").glob("[0-9]*.py"))
    assert names[-1].startswith(f"{head}_")


def test_unit_db_migrations_dir_missing_raises_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(db, "__file__", str(tmp_path / "a" / "b" / "c" / "db.py"))
    with pytest.raises(ConfigError):
        db.migrations_dir()


def test_unit_db_database_revision_none_when_never_migrated(engine: Engine) -> None:
    assert db.database_revision(engine) is None
    assert db.migrations_at_head(engine) is False


def test_unit_db_migrations_at_head_true_only_at_head(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num varchar(32) NOT NULL)"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('0001')"))
    assert db.migrations_at_head(engine) is False
    with engine.begin() as conn:
        conn.execute(text("UPDATE alembic_version SET version_num = :v"), {"v": db.head_revision()})
    assert db.migrations_at_head(engine) is True


def test_unit_db_migrate_upgrades_on_the_supplied_connection(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    upgrade = MagicMock()
    monkeypatch.setattr(db.command, "upgrade", upgrade)
    assert db.migrate(engine, "0001") is None
    config, revision = upgrade.call_args.args
    assert revision == "0001"
    assert config.attributes["connection"] is not None


def test_unit_db_migrate_takes_advisory_lock_on_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = MagicMock()
    connection.dialect.name = "postgresql"
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = connection
    monkeypatch.setattr(db.command, "upgrade", MagicMock())
    monkeypatch.setattr(db, "database_revision", lambda _e: "0002")
    assert db.migrate(engine) == "0002"
    statement = str(connection.execute.call_args.args[0])
    assert "pg_advisory_xact_lock" in statement
    assert connection.execute.call_args.args[1] == {"key": "supertrends.migrate"}
