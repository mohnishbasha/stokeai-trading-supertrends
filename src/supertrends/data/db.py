# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Engine, session, and migration helpers (ARCHITECTURE section 5.4).

The engine is built from `Settings.database_url` (SUPERTRENDS_DATABASE_URL); credentials are
never hard-coded. Migrations run under a transaction-scoped advisory lock so concurrent
migration Jobs serialize, and `migrations_at_head` backs the `/readyz` check.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from supertrends.errors import ConfigError
from supertrends.settings import Settings, load_settings

MIGRATE_LOCK_KEY = "supertrends.migrate"
_DRIVER_ALIASES = ("postgresql", "postgres")


def normalize_database_url(url: str) -> str:
    """Return a SQLAlchemy URL that uses the psycopg 3 driver for bare postgres URLs."""
    parsed = make_url(url)
    if parsed.drivername in _DRIVER_ALIASES:
        parsed = parsed.set(drivername="postgresql+psycopg")
    return parsed.render_as_string(hide_password=False)


def create_db_engine(settings: Settings | None = None, *, url: str | None = None) -> Engine:
    """Build an engine from `url`, else from `settings.database_url`, else the environment."""
    raw = url or (settings or load_settings()).database_url.get_secret_value()
    return create_engine(normalize_database_url(raw), pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Process-wide engine created lazily from the environment."""
    return create_db_engine()


def reset_engine() -> None:
    """Dispose and forget the cached engine (tests and settings reloads)."""
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    """Transactional session: commit on success, roll back on any exception, always close."""
    session = sessionmaker(bind=engine or get_engine(), expire_on_commit=False)()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def migrations_dir() -> Path:
    """Locate the bundled `migrations/` directory (working directory first, then the repo)."""
    candidates = (Path.cwd() / "migrations", Path(__file__).resolve().parents[3] / "migrations")
    for candidate in candidates:
        if (candidate / "env.py").is_file():
            return candidate
    msg = "migrations directory not found (expected ./migrations with env.py)"
    raise ConfigError(msg)


def alembic_config() -> Config:
    """Alembic config pointing at the bundled migrations; no database URL is stored in it."""
    config = Config()
    config.set_main_option("script_location", str(migrations_dir()))
    return config


def head_revision() -> str:
    """The head revision bundled in this build."""
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    if head is None:  # pragma: no cover (the repository always ships revisions)
        msg = "no migration revisions found"
        raise ConfigError(msg)
    return head


def database_revision(engine: Engine) -> str | None:
    """The revision recorded in the database, or None if it was never migrated.

    Raises `sqlalchemy.exc.OperationalError` when the database is unreachable, so callers can
    tell "unreachable" from "behind".
    """
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def migrations_at_head(engine: Engine) -> bool:
    """True when the database revision equals the head revision bundled in the image."""
    return database_revision(engine) == head_revision()


def migrate(engine: Engine, revision: str = "head") -> str | None:
    """Upgrade the database to `revision` under an advisory lock; return the resulting revision."""
    config = alembic_config()
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": MIGRATE_LOCK_KEY}
            )
        config.attributes["connection"] = connection
        command.upgrade(config, revision)
    return database_revision(engine)
