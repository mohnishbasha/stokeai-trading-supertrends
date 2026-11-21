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


def test_smoke_latest_recommendations_have_bounded_picks_with_evidence(
    client: httpx.Client,
) -> None:
    """TS-DEP-130: at most 3 buys and 2 sells, each with evidence; skips until the API exists.

    The recommendations API (S3-T09) and the run trigger (S3-T07) are not part of S3-T11. The
    check skips on 404 (route not built) and on an empty published run, and starts asserting as
    soon as both land. S3-T12 replaces it with the full smoke suite.
    """
    response = client.get("/api/v1/recommendations/latest")
    if response.status_code == 404:
        pytest.skip("GET /api/v1/recommendations/latest is not built yet (S3-T09)")
    response.raise_for_status()
    body = response.json()
    buys, sells = body.get("buys", []), body.get("sells", [])
    if not buys and not sells and not body.get("run_id"):
        pytest.skip("no published run yet (the run trigger lands with S3-T07)")
    assert len(buys) <= 3
    assert len(sells) <= 2
    for pick in [*buys, *sells]:
        assert pick.get("evidence")
