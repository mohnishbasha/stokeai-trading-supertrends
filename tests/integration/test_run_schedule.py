# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""A scheduled run on a holiday publishes nothing, against real Postgres (TS-OPS-011; S3-T10).

Runs only when SUPERTRENDS_IT_DATABASE_URL is set.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from alembic import command
from sqlalchemy import Engine, func, select
from typer.testing import CliRunner

from supertrends.cli.main import app
from supertrends.data import db
from supertrends.data.models import Run
from supertrends.runs import dates

URL = os.environ.get("SUPERTRENDS_IT_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="set SUPERTRENDS_IT_DATABASE_URL to run")


def _downgrade(engine: Engine) -> None:
    config = db.alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = db.create_db_engine(url=URL)
    _downgrade(eng)
    db.migrate(eng)
    yield eng
    _downgrade(eng)
    eng.dispose()


def test_it_runs_daily_on_a_holiday_exits_0_and_writes_no_run_row(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERTRENDS_DATABASE_URL", URL)
    monkeypatch.setattr(dates, "utc_now", lambda: datetime(2026, 11, 26, 22, 30, tzinfo=UTC))
    result = CliRunner().invoke(app, ["run", "daily"])
    assert result.exit_code == 0, result.output
    assert "market closed" in result.output
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Run)) == 0
