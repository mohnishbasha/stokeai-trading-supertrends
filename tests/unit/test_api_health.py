# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Liveness and readiness endpoints (Sprint 0 skeleton)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from supertrends.api.app import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SUPERTRENDS_VERSION", "0.1.0")
    monkeypatch.setenv("SUPERTRENDS_COMMIT", "abc1234")
    return TestClient(create_app(), base_url="http://localhost")


def test_api_healthz_returns_status_ok_version_and_commit(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0", "commit": "abc1234"}


def test_api_serves_ui_bundle_from_ui_dir(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>Super Trends</h1>")
    client = TestClient(create_app(ui_dir=tmp_path), base_url="http://localhost")
    response = client.get("/")
    assert response.status_code == 200
    assert "Super Trends" in response.text
    assert client.get("/healthz").json()["status"] == "ok"


def test_api_ui_dir_defaults_to_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "index.html").write_text("from env")
    monkeypatch.setenv("SUPERTRENDS_UI_DIR", str(tmp_path))
    assert TestClient(create_app(), base_url="http://localhost").get("/").text == "from env"


def test_api_without_ui_bundle_still_serves_health(tmp_path: Path) -> None:
    client = TestClient(create_app(ui_dir=tmp_path / "missing"), base_url="http://localhost")
    assert client.get("/").status_code == 404
    assert client.get("/healthz").status_code == 200
