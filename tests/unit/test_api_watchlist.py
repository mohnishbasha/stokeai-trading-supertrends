# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Watchlist HTTP contract (TS-WL, TS-API; SQLite stand-in, no network)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from supertrends.api.app import create_app
from supertrends.api.routes import watchlist as routes
from supertrends.data import watchlist as wl
from supertrends.data.models import WATCHLIST_ITEM_CAP
from supertrends.settings import Settings

TOKEN = "test-token-123"  # noqa: S105
AUTH = {"Authorization": f"Bearer {TOKEN}"}
PROBLEM = "application/problem+json"


class Unknown:
    """Resolver that rejects NOPE and accepts everything else."""

    def resolve_symbol(self, symbol: str) -> wl.PermissiveSymbol | None:
        return None if symbol == "NOPE" else wl.PermissiveSymbol(name=f"{symbol} Inc")


@pytest.fixture
def client(watchlist_engine: Engine) -> TestClient:
    factory = sessionmaker(bind=watchlist_engine, expire_on_commit=False)

    def _session() -> Iterator[Session]:
        with factory() as session:
            yield session

    with factory() as session:
        assert wl.seed_default_watchlist(session, wl.PermissiveResolver()) is not None
        session.commit()
    app = create_app(settings=Settings(api_token=TOKEN))  # type: ignore[arg-type]
    app.dependency_overrides[routes.get_session] = _session
    app.dependency_overrides[routes.get_symbol_resolver] = Unknown
    return TestClient(app, base_url="http://localhost")


def _problem(response: Any, status: int, slug: str) -> dict[str, Any]:
    assert response.status_code == status
    assert response.headers["content-type"].startswith(PROBLEM)
    body = response.json()
    assert body["type"] == f"urn:supertrends:problem:{slug}"
    assert body["status"] == status
    assert body["request_id"]
    assert response.headers["x-request-id"] == body["request_id"]
    return body  # type: ignore[no-any-return]


def test_contract_api_watchlist_read_without_token_returns_200(client: TestClient) -> None:
    response = client.get("/api/v1/watchlist")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "name", "count", "max", "groups", "items", "benchmarks"}
    assert (body["name"], body["count"], body["max"]) == ("default", 199, 300)
    assert body["benchmarks"] == ["SPY", "QQQ"]
    assert len(body["groups"]) == 14
    assert set(body["groups"][0]) == {"slug", "name", "position", "symbols"}
    assert set(body["items"][0]) == {
        "symbol", "name", "type", "scored", "resolution", "resolution_reason", "added_at", "groups"
    }  # fmt: skip


def test_contract_api_watchlist_unknown_query_parameter_returns_422(client: TestClient) -> None:
    body = _problem(client.get("/api/v1/watchlist?foo=1"), 422, "validation-error")
    assert body["errors"][0]["loc"] == ["query", "foo"]


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/v1/watchlist/items", {"symbol": "ABC"}),
        ("delete", "/api/v1/watchlist/items/NVDA", None),
        ("put", "/api/v1/watchlist/items/NVDA/groups", {"groups": []}),
        ("post", "/api/v1/watchlist/groups", {"slug": "g", "name": "G"}),
        ("delete", "/api/v1/watchlist/groups/semis", None),
    ],
)
def test_contract_api_watchlist_write_without_token_returns_401(
    client: TestClient, method: str, path: str, payload: dict[str, Any] | None
) -> None:
    for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic abc"}):
        response = client.request(method, path, json=payload, headers=headers)
        _problem(response, 401, "unauthorized")
        assert response.headers["www-authenticate"] == "Bearer"
    assert client.get("/api/v1/watchlist").json()["count"] == 199  # nothing changed


def test_contract_api_watchlist_add_item_returns_201_with_location(client: TestClient) -> None:
    response = client.post(
        "/api/v1/watchlist/items", json={"symbol": "zzco", "groups": ["fab-7"]}, headers=AUTH
    )
    assert response.status_code == 201
    assert response.headers["location"] == "/api/v1/watchlist"
    body = response.json()
    assert body["symbol"] == "ZZCO"
    assert (body["name"], body["scored"], body["resolution"]) == ("ZZCO Inc", True, "resolved")
    assert body["groups"] == ["fab-7"]
    listed = client.get("/api/v1/watchlist").json()
    assert listed["count"] == 200
    assert "ZZCO" in next(g for g in listed["groups"] if g["slug"] == "fab-7")["symbols"]


def test_contract_api_watchlist_add_ticker_301_returns_422(client: TestClient) -> None:
    for n in range(WATCHLIST_ITEM_CAP - 199):
        r = client.post("/api/v1/watchlist/items", json={"symbol": f"Z{n}"}, headers=AUTH)
        assert r.status_code == 201
    response = client.post("/api/v1/watchlist/items", json={"symbol": "ONEMORE"}, headers=AUTH)
    body = _problem(response, 422, "watchlist-full")
    assert "300" in body["detail"]
    assert client.get("/api/v1/watchlist").json()["count"] == 300


def test_contract_api_watchlist_add_item_errors(client: TestClient) -> None:
    dup = client.post("/api/v1/watchlist/items", json={"symbol": "NVDA"}, headers=AUTH)
    _problem(dup, 409, "already-exists")
    unresolved = client.post("/api/v1/watchlist/items", json={"symbol": "NOPE"}, headers=AUTH)
    assert "NOPE" in _problem(unresolved, 422, "symbol-unresolved")["detail"]
    bad = client.post("/api/v1/watchlist/items", json={"symbol": "1bad"}, headers=AUTH)
    assert _problem(bad, 422, "validation-error")["errors"][0]["loc"] == ["body", "symbol"]
    extra = client.post("/api/v1/watchlist/items", json={"symbol": "ABC", "x": 1}, headers=AUTH)
    _problem(extra, 422, "validation-error")
    group = client.post(
        "/api/v1/watchlist/items", json={"symbol": "ABC", "groups": ["nope"]}, headers=AUTH
    )
    _problem(group, 422, "validation-error")
    malformed = client.post(
        "/api/v1/watchlist/items",
        content=b"{not json",
        headers={**AUTH, "Content-Type": "application/json"},
    )
    _problem(malformed, 400, "bad-request")
    assert client.get("/api/v1/watchlist").json()["count"] == 199


def test_contract_api_watchlist_delete_item_204_then_404(client: TestClient) -> None:
    assert client.delete("/api/v1/watchlist/items/nvda", headers=AUTH).status_code == 204
    _problem(client.delete("/api/v1/watchlist/items/NVDA", headers=AUTH), 404, "not-found")
    _problem(client.delete("/api/v1/watchlist/items/1bad", headers=AUTH), 422, "validation-error")
    listed = client.get("/api/v1/watchlist").json()
    assert "NVDA" not in {i["symbol"] for i in listed["items"]}
    assert all("NVDA" not in g["symbols"] for g in listed["groups"])


def test_contract_api_watchlist_put_groups_replaces_memberships(client: TestClient) -> None:
    ok = client.put(
        "/api/v1/watchlist/items/NVDA/groups", json={"groups": ["fab-7", "semis"]}, headers=AUTH
    )
    assert ok.status_code == 200
    assert ok.json()["groups"] == ["fab-7", "semis"]
    cleared = client.put("/api/v1/watchlist/items/NVDA/groups", json={"groups": []}, headers=AUTH)
    assert cleared.json()["groups"] == []
    _problem(
        client.put("/api/v1/watchlist/items/NVDA/groups", json={"groups": ["zzz"]}, headers=AUTH),
        422,
        "validation-error",
    )
    _problem(
        client.put("/api/v1/watchlist/items/NOPE1/groups", json={"groups": []}, headers=AUTH),
        404,
        "not-found",
    )


def test_contract_api_watchlist_group_create_and_delete_keeps_items(client: TestClient) -> None:
    created = client.post(
        "/api/v1/watchlist/groups",
        json={"slug": "mine", "name": "Mine", "position": 3},
        headers=AUTH,
    )
    assert created.status_code == 201
    assert created.json() == {"slug": "mine", "name": "Mine", "position": 3, "symbols": []}
    _problem(
        client.post("/api/v1/watchlist/groups", json={"slug": "mine", "name": "M"}, headers=AUTH),
        409,
        "already-exists",
    )
    _problem(
        client.post(
            "/api/v1/watchlist/groups", json={"slug": "Bad Slug", "name": "M"}, headers=AUTH
        ),
        422,
        "validation-error",
    )
    client.put("/api/v1/watchlist/items/NVDA/groups", json={"groups": ["mine"]}, headers=AUTH)
    assert client.delete("/api/v1/watchlist/groups/mine", headers=AUTH).status_code == 204
    _problem(client.delete("/api/v1/watchlist/groups/mine", headers=AUTH), 404, "not-found")
    listed = client.get("/api/v1/watchlist").json()
    assert "NVDA" in {i["symbol"] for i in listed["items"]}
    assert "mine" not in {g["slug"] for g in listed["groups"]}


def test_contract_api_watchlist_endpoints_before_seed_return_404_problem(
    watchlist_engine: Engine,
) -> None:
    factory = sessionmaker(bind=watchlist_engine, expire_on_commit=False)

    def _session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app = create_app(settings=Settings(api_token=TOKEN))  # type: ignore[arg-type]
    app.dependency_overrides[routes.get_session] = _session
    _problem(
        TestClient(app, base_url="http://localhost").get("/api/v1/watchlist"), 404, "not-found"
    )


def test_unit_api_default_symbol_resolver_is_permissive() -> None:
    assert routes.get_symbol_resolver().resolve_symbol("ABC") is not None
