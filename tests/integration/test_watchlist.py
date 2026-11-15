# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Watchlist seed, service, and HTTP API end to end against real Postgres (S1-T07).

Runs only when SUPERTRENDS_IT_DATABASE_URL is set. Every test migrates in its own fixture and
downgrades to base afterwards, so no state is assumed or left behind.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from supertrends.api.app import create_app
from supertrends.api.routes import watchlist as routes
from supertrends.api.security import get_settings
from supertrends.data import db
from supertrends.data import watchlist as wl
from supertrends.data.models import Ticker, WatchlistGroupMember, WatchlistItem
from supertrends.settings import Settings

URL = os.environ.get("SUPERTRENDS_IT_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="set SUPERTRENDS_IT_DATABASE_URL to run")

TOKEN = "it-token"  # noqa: S105
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class Provider:
    """Reference data that does not know SQ, XIACF, and ZZUNKNOWN."""

    unknown = frozenset({"SQ", "XIACF", "ZZUNKNOWN"})

    def resolve_symbol(self, symbol: str) -> wl.PermissiveSymbol | None:
        if symbol in self.unknown:
            return None
        return wl.PermissiveSymbol(
            name=f"{symbol} Corp", type="etf" if symbol == "SPY" else "stock"
        )


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


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s


@pytest.fixture
def client(engine: Engine, session: Session) -> TestClient:
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def _session() -> Iterator[Session]:
        with factory() as s:
            yield s

    assert wl.seed_default_watchlist(session, Provider()) is not None
    session.commit()
    app = create_app()
    app.dependency_overrides[routes.get_session] = _session
    app.dependency_overrides[routes.get_symbol_resolver] = Provider
    app.dependency_overrides[get_settings] = lambda: Settings(api_token=TOKEN)  # type: ignore[arg-type]
    return TestClient(app)


def test_it_watchlist_seed_unresolvable_symbol_marked_unresolved_with_reason(
    session: Session,
) -> None:
    ticker = session.get(Ticker, "SQ")
    assert ticker is None  # nothing seeded yet
    result = wl.seed_default_watchlist(session, Provider())
    assert result is not None
    session.commit()
    assert set(result.unresolved) == {"SQ", "XIACF"}
    sq = session.get(Ticker, "SQ")
    assert sq is not None
    assert sq.resolution == "unresolved"
    assert sq.resolution_reason
    assert session.get(Ticker, "XYZ") is None  # never substituted
    assert "SQ" not in wl.symbols_to_ingest(session)
    assert session.get(Ticker, "000660") is None  # fails the tickers symbol CHECK; reported
    assert set(result.rejected) == {"000660"}


def test_it_watchlist_seed_second_start_does_not_reseed_or_duplicate(session: Session) -> None:
    assert wl.seed_default_watchlist(session, Provider()) is not None
    session.commit()
    wl.remove_item(session, "NVDA")
    session.commit()
    assert wl.seed_default_watchlist(session, Provider()) is None
    assert session.get(WatchlistItem, (1, "NVDA")) is None
    count = session.scalar(select(func.count()).select_from(WatchlistItem))
    assert count == 198


def test_it_watchlist_seed_symbol_in_three_groups_stored_once(session: Session) -> None:
    wl.seed_default_watchlist(session, Provider())
    session.commit()
    tickers = session.scalar(
        select(func.count()).select_from(Ticker).where(Ticker.symbol == "TSLA")
    )
    members = session.scalar(
        select(func.count())
        .select_from(WatchlistGroupMember)
        .where(WatchlistGroupMember.symbol == "TSLA")
    )
    assert tickers == 1
    assert members == 4  # adam-khoo-ai-robotics, whatsapp-group, fab-7, trump-stocks


def test_it_watchlist_api_end_to_end_against_postgres(client: TestClient) -> None:
    listed = client.get("/api/v1/watchlist")
    assert listed.status_code == 200
    assert (listed.json()["count"], len(listed.json()["groups"])) == (199, 14)

    assert client.post("/api/v1/watchlist/items", json={"symbol": "ABC"}).status_code == 401
    unresolved = client.post("/api/v1/watchlist/items", json={"symbol": "ZZUNKNOWN"}, headers=AUTH)
    assert unresolved.status_code == 422
    assert unresolved.json()["type"].endswith("symbol-unresolved")

    created = client.post(
        "/api/v1/watchlist/groups", json={"slug": "mine", "name": "Mine"}, headers=AUTH
    )
    assert created.status_code == 201
    added = client.post(
        "/api/v1/watchlist/items", json={"symbol": "ABC", "groups": ["mine"]}, headers=AUTH
    )
    assert added.status_code == 201
    assert added.json()["groups"] == ["mine"]
    assert (
        client.post("/api/v1/watchlist/items", json={"symbol": "ABC"}, headers=AUTH).status_code
        == 409
    )
    put = client.put(
        "/api/v1/watchlist/items/ABC/groups", json={"groups": ["mine", "fab-7"]}, headers=AUTH
    )
    assert put.json()["groups"] == ["mine", "fab-7"]
    assert client.delete("/api/v1/watchlist/groups/mine", headers=AUTH).status_code == 204
    assert client.delete("/api/v1/watchlist/items/ABC", headers=AUTH).status_code == 204
    assert client.delete("/api/v1/watchlist/items/ABC", headers=AUTH).status_code == 404
    assert client.get("/api/v1/watchlist").json()["count"] == 199


def test_it_watchlist_add_ticker_301_returns_422_against_postgres(client: TestClient) -> None:
    for n in range(101):
        r = client.post("/api/v1/watchlist/items", json={"symbol": f"Q{n}"}, headers=AUTH)
        assert r.status_code == 201
    response = client.post("/api/v1/watchlist/items", json={"symbol": "QOVER"}, headers=AUTH)
    assert response.status_code == 422
    assert response.json()["type"].endswith("watchlist-full")
    assert client.get("/api/v1/watchlist").json()["count"] == 300


def test_it_watchlist_add_unknown_symbol_provider_validation_returns_422_with_message(
    client: TestClient,
) -> None:
    response = client.post("/api/v1/watchlist/items", json={"symbol": "ZZUNKNOWN"}, headers=AUTH)
    assert response.status_code == 422
    assert "ZZUNKNOWN" in response.json()["detail"]
    assert client.get("/api/v1/watchlist").json()["count"] == 199


def test_it_watchlist_benchmarks_spy_qqq_ingested_even_if_removed(
    client: TestClient, session: Session
) -> None:
    assert client.delete("/api/v1/watchlist/items/SPY", headers=AUTH).status_code == 204
    assert client.delete("/api/v1/watchlist/items/QQQ", headers=AUTH).status_code == 204
    session.expire_all()
    ingest = wl.symbols_to_ingest(session)
    assert {"SPY", "QQQ"} <= set(ingest)
    assert "CITI" not in ingest
    assert "VIX" in ingest
    assert "SQ" not in ingest
