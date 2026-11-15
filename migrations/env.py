# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Alembic environment. Online mode only; the URL comes from SUPERTRENDS_DATABASE_URL.

`supertrends.data.db.migrate` passes an open connection through `config.attributes`, which is
how the advisory lock and the migration share one transaction. The plain `alembic` CLI builds
its own engine from the same settings.
"""

from alembic import context

from supertrends.data.db import create_db_engine
from supertrends.data.models import Base

target_metadata = Base.metadata


def _run(connection: object) -> None:
    context.configure(
        connection=connection,  # type: ignore[arg-type]
        target_metadata=target_metadata,
        include_schemas=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations on the supplied connection, or on one from the configured engine."""
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = create_db_engine()
    try:
        with engine.begin() as new_connection:
            _run(new_connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    msg = "offline migrations are not supported; run against a database"
    raise RuntimeError(msg)
run_migrations_online()
