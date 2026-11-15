# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""/readyz against real Postgres (TS-API-002, TS-API-003, TS-SEC-006).

Runs only when SUPERTRENDS_IT_DATABASE_URL is set. Leaves the database at base.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from supertrends.api.app import create_app
from supertrends.data import db
from supertrends.settings import Settings

URL = os.environ.get("SUPERTRENDS_IT_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="set SUPERTRENDS_IT_DATABASE_URL to run")


def _downgrade_base(engine: Engine) -> None:
    config = db.alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = db.create_db_engine(url=URL)
    _downgrade_base(eng)
    yield eng
    _downgrade_base(eng)
    eng.dispose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(_env_file=None, database_url=URL)  # type: ignore[arg-type]
    with TestClient(create_app(settings=settings), base_url="http://localhost") as c:
        yield c


def test_api_readyz_unmigrated_database_returns_503_behind(
    engine: Engine, client: TestClient
) -> None:
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["reason"] == "migrations_behind"


def test_api_readyz_at_head_returns_200_and_metrics_hide_dsn(
    engine: Engine, client: TestClient
) -> None:
    db.migrate(engine)
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert URL not in client.get("/metrics").text
