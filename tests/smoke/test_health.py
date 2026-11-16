# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Smoke suite against a running deployment at SMOKE_BASE_URL (make smoke).

One suite for Compose, kind, and Stoke. Sprint 3 (S3-T12) extends it with the run,
recommendations, analysis, and watchlist checks.
"""

import os

import httpx
import pytest

BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://localhost:8080")


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=10.0)


def test_smoke_healthz_reports_ok_with_version_and_commit(client: httpx.Client) -> None:
    body = client.get("/healthz").raise_for_status().json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["commit"]


def test_smoke_readyz_reports_ready(client: httpx.Client) -> None:
    assert client.get("/readyz").raise_for_status().json()["status"] == "ready"


def test_smoke_ui_is_served(client: httpx.Client) -> None:
    response = client.get("/").raise_for_status()
    assert '<div id="root">' in response.text
