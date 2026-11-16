# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""API skeleton: readiness, metrics, request IDs, problem responses, Host allowlist (S1-T08)."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from pydantic import BaseModel

from supertrends.api import app as app_module
from supertrends.api import security
from supertrends.api.app import create_app
from supertrends.api.security import require_write_token
from supertrends.settings import Settings

DOWN_URL = "postgresql+psycopg://u:hunter2pw@127.0.0.1:1/x"  # gitleaks:allow
TOKEN = "tok-abcdef-123456"  # noqa: S105  # gitleaks:allow


def _settings() -> Settings:
    return Settings(_env_file=None, database_url=DOWN_URL, api_token=TOKEN)  # type: ignore[arg-type]


class Body(BaseModel):
    n: int


@pytest.fixture
def client() -> TestClient:
    app = create_app(Path("/nonexistent-ui"), settings=_settings())
    router = APIRouter(prefix="/api/v1")

    @router.post("/_t/write", dependencies=[Depends(require_write_token)])
    def write(body: Body) -> dict[str, int]:
        return {"n": body.n}

    @router.get("/_t/boom")
    def boom() -> None:
        raise RuntimeError("secret internals hunter2pw")

    app.include_router(router)
    return TestClient(app, base_url="http://localhost", raise_server_exceptions=False)


def test_api_readyz_database_down_returns_503_problem_without_dsn(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"] == "urn:supertrends:problem:not-ready"
    assert body["reason"] == "database_unreachable"
    assert "hunter2pw" not in response.text
    assert "127.0.0.1" not in response.text


def test_api_readyz_migrations_behind_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module.db, "database_revision", lambda _e: "old")
    monkeypatch.setattr(app_module.db, "head_revision", lambda: "new")
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["reason"] == "migrations_behind"


def test_api_readyz_never_migrated_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module.db, "database_revision", lambda _e: None)
    monkeypatch.setattr(app_module.db, "head_revision", lambda: "new")
    assert client.get("/readyz").json()["reason"] == "migrations_behind"


def test_api_readyz_at_head_returns_200(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module.db, "database_revision", lambda _e: "rev")
    monkeypatch.setattr(app_module.db, "head_revision", lambda: "rev")
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_api_healthz_does_not_touch_database(client: TestClient) -> None:
    assert client.get("/healthz").status_code == 200


def test_api_request_id_generated_and_echoed(client: TestClient) -> None:
    generated = client.get("/healthz").headers["x-request-id"]
    assert len(generated) >= 16
    echoed = client.get("/healthz", headers={"X-Request-ID": "abc-123_DEF"})
    assert echoed.headers["x-request-id"] == "abc-123_DEF"


def test_api_unsafe_request_id_replaced(client: TestClient) -> None:
    response = client.get("/healthz", headers={"X-Request-ID": "bad id with spaces!"})
    assert response.headers["x-request-id"] != "bad id with spaces!"


def test_api_problem_json_for_unknown_route_has_required_members(client: TestClient) -> None:
    response = client.get("/api/v1/nope", headers={"X-Request-ID": "rid-1"})
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert {"type", "title", "status", "detail", "instance", "request_id"} <= body.keys()
    assert body["type"] == "urn:supertrends:problem:not-found"
    assert body["request_id"] == "rid-1"


def test_api_problem_json_method_not_allowed(client: TestClient) -> None:
    response = client.post("/healthz")
    assert response.status_code == 405
    assert response.json()["type"].endswith(":method-not-allowed")


def test_api_validation_error_returns_422_problem_with_errors(client: TestClient) -> None:
    response = client.post(
        "/api/v1/_t/write", json={"n": "x"}, headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert response.status_code == 422
    body = response.json()
    assert body["type"].endswith(":validation-error")
    assert body["errors"][0]["loc"][0] == "body"
    assert response.headers["content-type"].startswith("application/problem+json")


def test_api_unhandled_error_returns_500_without_stack_or_secret(client: TestClient) -> None:
    response = client.get("/api/v1/_t/boom")
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith(":internal")
    assert "hunter2pw" not in response.text
    assert "Traceback" not in response.text
    assert "x-request-id" in response.headers


def test_api_write_without_token_returns_401_with_www_authenticate(client: TestClient) -> None:
    response = client.post("/api/v1/_t/write", json={"n": 1})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["type"].endswith(":unauthorized")


def test_api_write_wrong_token_returns_401(client: TestClient) -> None:
    response = client.post(
        "/api/v1/_t/write", json={"n": 1}, headers={"Authorization": "Bearer nope"}
    )
    assert response.status_code == 401


def test_api_write_right_token_passes(client: TestClient) -> None:
    response = client.post(
        "/api/v1/_t/write", json={"n": 1}, headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert response.status_code == 200


def test_security_token_compare_uses_constant_time_function() -> None:
    assert "hmac.compare_digest" in inspect.getsource(security)


def test_api_metrics_exposes_http_counters_by_route_template(client: TestClient) -> None:
    client.get("/healthz")
    client.get("/api/v1/does-not-exist-123")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    assert 'supertrends_http_requests_total{method="GET",route="/healthz",status="200"}' in text
    assert "supertrends_http_request_duration_seconds_bucket" in text
    assert "supertrends_build_info" in text
    assert "does-not-exist-123" not in text
    assert "hunter2pw" not in text
    assert TOKEN not in text


def test_api_host_allowlist_rejects_foreign_host_with_421(client: TestClient) -> None:
    response = client.get("/api/v1/nope", headers={"Host": "evil.example.com"})
    assert response.status_code == 421
    assert response.json()["type"].endswith(":misdirected-request")
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.parametrize("path", ["/healthz", "/metrics"])
def test_api_host_allowlist_exempts_probe_paths(client: TestClient, path: str) -> None:
    assert client.get(path, headers={"Host": "10.1.2.3:8080"}).status_code == 200


def test_api_host_allowlist_readyz_exempt(client: TestClient) -> None:
    assert client.get("/readyz", headers={"Host": "10.1.2.3:8080"}).status_code == 503


def test_api_host_allowlist_accepts_listed_host_with_port(client: TestClient) -> None:
    assert client.get("/api/v1/nope", headers={"Host": "LocalHost:8080"}).status_code == 404
