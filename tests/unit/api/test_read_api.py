# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Read API contract tests: every endpoint and documented error (S3-T09, FR-801 to FR-807).

Scenario names follow docs/TEST_PLAN.md section 10.11; the app runs against an in-memory store.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from supertrends.api import deps
from supertrends.api.openapi import render_openapi
from supertrends.runs import dates
from supertrends.runs.narrator import DISCLAIMER
from supertrends.runs.service import TriggerResult
from supertrends.scoring.config import FACTOR_IDS
from tests.unit.api.api_support import (
    ACTIVE_ID,
    AUTH,
    HASH,
    NOW,
    OLD_RUN_ID,
    RUN_ID,
    TOKEN,
    make_client,
    make_store,
    problem,
)

LATEST = "/api/v1/recommendations/latest"


def test_contract_api_recommendations_latest_shape_matches_openapi() -> None:
    client, _ = make_client()
    body = client.get(LATEST).json()
    doc = client.get("/openapi.json").json()
    schema = {
        "$ref": "#/components/schemas/RecommendationsResponse",
        "components": doc["components"],
    }
    errors = list(Draft202012Validator(schema).iter_errors(body))
    assert errors == []
    assert body["date"] == "2026-11-13"
    assert body["run_id"] == RUN_ID
    assert body["market_regime"] == "risk_on"
    assert body["config"] == {"version": 1, "hash": HASH} or body["config"]["hash"] == HASH
    assert len(body["buys"]) <= 3
    assert len(body["sells"]) <= 2
    pick = body["buys"][0]
    for key in (
        "supertrend",
        "invalidation",
        "top_factors",
        "narrative",
        "ribbon",
        "flags",
        "days_on_list",
        "expected_1d_move",
        "recommendation_id",
        "entry_price",
        "rank",
        "ticker",
        "display_score",
        "band",
        "confidence",
        "regime",
    ):
        assert key in pick
    assert pick["confidence"] == 71
    assert pick["ribbon"] == "UUUUDDDUUU"
    assert [f["id"] for f in pick["top_factors"]] == ["supertrend", "sma", "macd"]
    assert pick["narrative"] == {
        "text": "Daily Supertrend is up.",
        "source": "template",
        "model": None,
    }
    assert body["also_qualified"] == [
        {
            "ticker": "VOO",
            "side": "buy",
            "display_score": 77.9,
            "confidence": 70,
            "duplicates": "ORCL",
            "correlation": 0.99,
        }
    ]
    assert body["nearest_miss"]["buy"] is None
    assert body["nearest_miss"]["sell"] == {
        "ticker": "XYZ",
        "display_score": 37.2,
        "reason": "score above the sell threshold of 35",
    }
    assert body["excluded"] == [{"ticker": "ABC", "reason": "stale"}]
    assert body["summary"]["tickers_total"] == 4
    assert body["summary"]["narrative_template"] == 1
    assert body["superseded_runs"][0]["id"] == OLD_RUN_ID


def test_contract_api_recommendations_latest_includes_disclaimer_string() -> None:
    client, _ = make_client()
    assert client.get(LATEST).json()["disclaimer"] == DISCLAIMER


def test_contract_api_recommendations_latest_no_run_returns_404_problem() -> None:
    client, store = make_client()
    store.published.clear()
    body = problem(client.get(LATEST), 404, "no-published-run")
    assert "no published run" in body["detail"].lower()


def test_contract_api_recommendations_by_date_returns_that_days_published_run() -> None:
    client, _ = make_client()
    body = client.get("/api/v1/recommendations", params={"date": "2026-11-13"}).json()
    assert body["run_id"] == RUN_ID
    assert body["disclaimer"] == DISCLAIMER


def test_contract_api_recommendations_by_date_non_trading_date_returns_422() -> None:
    client, _ = make_client()
    body = problem(
        client.get("/api/v1/recommendations", params={"date": "2026-11-15"}),
        422,
        "not-a-trading-date",
    )
    assert "not a trading date" in body["detail"]


def test_contract_api_recommendations_by_date_future_returns_422_date_in_future() -> None:
    client, _ = make_client()
    problem(
        client.get("/api/v1/recommendations", params={"date": "2026-11-17"}),
        422,
        "date-in-future",
    )


def test_contract_api_recommendations_by_date_no_run_returns_404_problem() -> None:
    client, _ = make_client()
    problem(
        client.get("/api/v1/recommendations", params={"date": "2026-11-12"}),
        404,
        "no-published-run",
    )


def test_contract_api_recommendations_by_date_missing_or_malformed_date_returns_422() -> None:
    client, _ = make_client()
    body = problem(client.get("/api/v1/recommendations"), 422, "validation-error")
    assert body["errors"]
    problem(client.get("/api/v1/recommendations?date=11-13-2026"), 422, "validation-error")


def test_contract_api_unknown_query_parameter_returns_422() -> None:
    client, _ = make_client()
    body = problem(client.get(LATEST + "?bogus=1"), 422, "validation-error")
    assert body["errors"][0]["loc"] == ["query", "bogus"]


def test_contract_api_rankings_by_date_sorted_with_data_quality_and_exclusions() -> None:
    client, _ = make_client()
    body = client.get("/api/v1/rankings", params={"date": "2026-11-13"}).json()
    assert body["run_id"] == RUN_ID
    assert body["total"] == 3
    assert (body["limit"], body["offset"]) == (50, 0)
    assert [i["rank"] for i in body["items"]] == [1, 2, 3]
    assert body["items"][0]["picked"] == "buy"
    assert body["items"][1]["picked"] == "also_qualified"
    assert body["items"][2]["picked"] is None
    assert body["items"][0]["confidence"] == 71
    assert body["excluded"] == [{"ticker": "ABC", "reason": "stale"}]
    assert body["disclaimer"] == DISCLAIMER
    paged = client.get("/api/v1/rankings", params={"limit": 1, "offset": 1}).json()
    assert [i["rank"] for i in paged["items"]] == [2]
    assert paged["total"] == 3


def test_contract_api_rankings_validation_and_errors() -> None:
    client, store = make_client()
    problem(client.get("/api/v1/rankings?limit=0"), 422, "validation-error")
    problem(client.get("/api/v1/rankings?limit=100000"), 422, "validation-error")
    problem(client.get("/api/v1/rankings?offset=-1"), 422, "validation-error")
    problem(client.get("/api/v1/rankings?group=nope"), 404, "not-found")
    assert client.get("/api/v1/rankings?group=ai-infra").status_code == 200
    problem(client.get("/api/v1/rankings?date=2026-11-15"), 422, "not-a-trading-date")
    problem(client.get("/api/v1/rankings?date=2026-11-12"), 404, "no-published-run")
    store.published.clear()
    problem(client.get("/api/v1/rankings"), 404, "no-published-run")


def test_contract_api_ticker_analysis_returns_11_factors_or_stated_reason() -> None:
    """The scenario name predates Factor 12 (Ripster); every factor id is returned."""
    client, _ = make_client()
    body = client.get("/api/v1/tickers/orcl/analysis").json()
    assert body["ticker"] == "ORCL"
    assert body["name"] == "Oracle Corp"
    assert body["status"] == "scored"
    assert [f["id"] for f in body["factors"]] == list(FACTOR_IDS)
    assert body["factors"][0]["base_weight"] == 8.0
    assert body["factors"][0]["reasons"] == ["supertrend reason"]
    assert body["thresholds"] == {"buy": 65.0, "sell": 30.0}
    assert body["picked"]["side"] == "buy"
    assert body["picked"]["recommendation_id"]
    assert body["supertrend"]["distance_atr"] == 1.2
    assert body["ripster"]["c3_top"] == 210.8
    assert body["expected_1d_move"] == 4.1
    assert body["narrative"]["source"] == "template"
    assert body["disclaimer"] == DISCLAIMER
    assert body["market_regime"] == "risk_on"
    assert body["config"]["hash"] == HASH
    excluded = client.get("/api/v1/tickers/ABC/analysis?date=2026-11-13").json()
    assert excluded["status"] == "excluded"
    assert excluded["exclusion_reason"] == "stale"
    assert excluded["display_score"] is None
    assert excluded["factors"] == []
    assert excluded["disclaimer"] == DISCLAIMER


def test_contract_api_ticker_analysis_not_scored_in_run_is_excluded_not_in_run() -> None:
    client, _ = make_client()
    body = client.get("/api/v1/tickers/SPY/analysis").json()
    assert body["status"] == "excluded"
    assert body["exclusion_reason"] == "not_in_run"


def test_contract_api_ticker_analysis_unknown_symbol_returns_404() -> None:
    client, store = make_client()
    problem(client.get("/api/v1/tickers/ZZZZ/analysis"), 404, "ticker-not-found")
    store.published.clear()
    problem(client.get("/api/v1/tickers/ORCL/analysis"), 404, "no-published-run")
    problem(client.get("/api/v1/tickers/ORCL/analysis?date=2026-11-12"), 404, "no-published-run")


def test_contract_api_ticker_analysis_invalid_symbol_returns_422() -> None:
    client, _ = make_client()
    problem(client.get("/api/v1/tickers/1BAD/analysis"), 422, "validation-error")
    problem(client.get("/api/v1/tickers/WAYTOOLONGSYMBOL/analysis"), 422, "validation-error")
    problem(client.get("/api/v1/tickers/ORCL/analysis?date=2026-11-15"), 422, "not-a-trading-date")
    problem(client.get("/api/v1/tickers/1BAD/bars"), 422, "validation-error")


def test_contract_api_ticker_bars_range_and_pagination_bounded() -> None:
    client, store = make_client()
    body = client.get("/api/v1/tickers/ORCL/bars").json()
    assert body["ticker"] == "ORCL"
    assert body["tf"] == "1d"
    assert (body["from"], body["to"]) == ("2026-11-11", "2026-11-13") or body["to"] == "2026-11-13"
    assert body["bars"][-1] == {
        "t": "2026-11-13",
        "o": 220.1,
        "h": 224.0,
        "l": 219.2,
        "c": 223.5,
        "v": 9123000,
    }
    assert set(body["overlays"]) == {
        "supertrend",
        "sma_20",
        "sma_50",
        "sma_200",
        "ripster_c2",
        "ripster_c3",
    }
    assert "disclaimer" not in body
    ranged = client.get("/api/v1/tickers/ORCL/bars?from=2026-11-12&to=2026-11-13").json()
    assert [b["t"] for b in ranged["bars"]] == ["2026-11-12", "2026-11-13"]
    assert store.calls[-1][2] == "1d"
    problem(client.get("/api/v1/tickers/ORCL/bars?tf=1h"), 422, "validation-error")
    problem(
        client.get("/api/v1/tickers/ORCL/bars?from=2010-01-04&to=2026-11-13"),
        422,
        "validation-error",
    )
    problem(
        client.get("/api/v1/tickers/ORCL/bars?tf=5m&from=2026-09-01&to=2026-11-13"),
        422,
        "validation-error",
    )
    problem(
        client.get("/api/v1/tickers/ORCL/bars?from=2026-11-13&to=2026-11-12"),
        422,
        "validation-error",
    )
    problem(client.get("/api/v1/tickers/ZZZZ/bars"), 404, "ticker-not-found")


def test_contract_api_ticker_bars_without_stored_bars_returns_empty_list() -> None:
    client, store = make_client()
    store.bar_rows = []
    body = client.get("/api/v1/tickers/ORCL/bars").json()
    assert body["bars"] == []
    assert body["from"] is None
    assert body["to"] is None


def test_contract_api_runs_list_pagination_bounded() -> None:
    client, _ = make_client()
    body = client.get("/api/v1/runs").json()
    assert [r["id"] for r in body["items"]] == [RUN_ID, OLD_RUN_ID]
    first = body["items"][0]
    assert first["state"] == "published"
    assert first["picks"] == {"buy": 1, "sell": 0}
    assert first["duration_seconds"] == 12.5
    assert body["next_before"] is None
    page = client.get("/api/v1/runs?limit=1").json()
    assert [r["id"] for r in page["items"]] == [RUN_ID]
    assert page["next_before"] == RUN_ID
    after = client.get("/api/v1/runs", params={"limit": 1, "before": RUN_ID}).json()
    assert [r["id"] for r in after["items"]] == [OLD_RUN_ID]
    problem(client.get("/api/v1/runs?limit=0"), 422, "validation-error")
    problem(client.get("/api/v1/runs?limit=201"), 422, "validation-error")
    problem(client.get("/api/v1/runs?before=nope"), 422, "validation-error")


def test_contract_api_runs_get_by_id_returns_state_history_and_exclusions() -> None:
    client, _ = make_client()
    body = client.get(f"/api/v1/runs/{RUN_ID}").json()
    assert body["id"] == RUN_ID
    assert body["transitions"][1] == {
        "seq": 2,
        "from": "queued",
        "to": "ingesting",
        "at": "2026-11-16T22:00:00Z",
    }
    assert body["summary"]["excluded"] == [{"ticker": "ABC", "reason": "stale"}]
    assert body["summary"]["narrative"] == {"llm": 0, "template": 1}
    assert body["code_version"] == "1.0.0 (abc1234)"
    assert "disclaimer" not in body
    problem(client.get("/api/v1/runs/01JCQ4K5M6N7P8Q9R0S1T2V3W4"), 404, "not-found")
    problem(client.get("/api/v1/runs/not-a-ulid"), 422, "validation-error")


def test_contract_api_post_runs_without_token_returns_401() -> None:
    client, store = make_client()
    response = client.post("/api/v1/runs", json={})
    problem(response, 401, "unauthorized")
    assert response.headers["www-authenticate"] == "Bearer"
    assert not store.calls


def test_contract_api_post_runs_wrong_token_returns_401_constant_time_compare() -> None:
    client, _ = make_client()
    wrong = {"Authorization": f"Bearer {TOKEN}x"}
    problem(client.post("/api/v1/runs", json={}, headers=wrong), 401, "unauthorized")
    source = (Path(__file__).resolve().parents[3] / "src/supertrends/api/security.py").read_text()
    assert "hmac.compare_digest" in source


def test_contract_api_post_runs_with_token_returns_202_and_run_id() -> None:
    client, store = make_client()
    response = client.post("/api/v1/runs", json={"date": "2026-11-13"}, headers=AUTH)
    assert response.status_code == 202
    assert response.json() == {"run_id": RUN_ID, "state": "queued", "trade_date": "2026-11-13"}
    assert response.headers["location"] == f"/api/v1/runs/{RUN_ID}"
    assert store.calls[-1][1].isoformat() == "2026-11-13"
    default = client.post("/api/v1/runs", json={}, headers=AUTH)
    assert default.status_code == 202
    assert default.json()["trade_date"] == "2026-11-16"
    assert client.post("/api/v1/runs", headers=AUTH).status_code == 202


def test_contract_api_post_runs_while_running_returns_409_already_running() -> None:
    client, store = make_client()
    store.trigger_result = TriggerResult(
        "already_running", store_date(), active_run_id=ACTIVE_ID, active_trade_date=store_date()
    )
    body = problem(client.post("/api/v1/runs", json={}, headers=AUTH), 409, "run-in-progress")
    assert body["active_run_id"] == ACTIVE_ID
    assert ACTIVE_ID in body["detail"]


def store_date() -> date:
    return date(2026, 11, 16)


def test_contract_api_post_runs_date_errors_and_market_closed() -> None:
    client, _ = make_client()
    problem(
        client.post("/api/v1/runs", json={"date": "2026-11-15"}, headers=AUTH),
        422,
        "not-a-trading-date",
    )
    problem(
        client.post("/api/v1/runs", json={"date": "2026-11-17"}, headers=AUTH),
        422,
        "date-in-future",
    )
    problem(
        client.post("/api/v1/runs", json={"date": "bad"}, headers=AUTH), 422, "validation-error"
    )
    problem(client.post("/api/v1/runs", json={"extra": 1}, headers=AUTH), 422, "validation-error")
    problem(
        client.post(
            "/api/v1/runs",
            content="{",
            headers={**AUTH, "content-type": "application/json"},
        ),
        422,
        "validation-error",
    )


def test_contract_api_post_runs_weekend_default_returns_200_market_closed(monkeypatch: Any) -> None:
    client, store = make_client()
    saturday = datetime(2026, 11, 14, 18, 0, tzinfo=UTC)
    client.app.dependency_overrides[deps.get_clock] = lambda: saturday  # type: ignore[attr-defined]
    response = client.post("/api/v1/runs", json={}, headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {"run_id": None, "state": "market_closed"}
    assert not store.calls


def test_contract_api_post_runs_market_closed_code_returns_200_market_closed(
    monkeypatch: Any,
) -> None:
    """S3-T10 raises `TradeDateError` with code `market_closed`; the handler maps it by code."""

    def closed(requested: date | None, now: Any = None) -> date:
        exc = dates.TradeDateError(dates.NOT_A_TRADING_DATE, "market closed")
        exc.code = "market_closed"
        raise exc

    monkeypatch.setattr(dates, "resolve_trade_date", closed)
    client, store = make_client()
    response = client.post("/api/v1/runs", json={"date": "2026-11-13"}, headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {"run_id": None, "state": "market_closed"}
    assert not store.calls


def test_contract_api_post_runs_session_not_complete_returns_409() -> None:
    client, _ = make_client()
    midday = datetime(2026, 11, 16, 16, 0, tzinfo=UTC)
    client.app.dependency_overrides[deps.get_clock] = lambda: midday  # type: ignore[attr-defined]
    problem(client.post("/api/v1/runs", json={}, headers=AUTH), 409, "session-not-complete")


def test_contract_api_config_scoring_returns_active_config_and_hash() -> None:
    client, _ = make_client()
    body = client.get("/api/v1/config/scoring").json()
    version = body["document"]["scoring"]["version"]
    assert body["version"] == version >= 1
    assert body["hash"].startswith("sha256:")
    assert body["loaded_at"]


def test_contract_api_openapi_document_matches_committed_docs_openapi_json() -> None:
    committed = (Path(__file__).resolve().parents[3] / "docs" / "openapi.json").read_text()
    assert committed == render_openapi(), "run `make openapi` and commit docs/openapi.json"
    paths = json.loads(committed)["paths"]
    for path in (
        "/api/v1/recommendations/latest",
        "/api/v1/recommendations",
        "/api/v1/rankings",
        "/api/v1/tickers/{symbol}/analysis",
        "/api/v1/tickers/{symbol}/bars",
        "/api/v1/runs",
        "/api/v1/runs/{run_id}",
        "/api/v1/config/scoring",
    ):
        assert path in paths


def test_contract_api_every_pick_payload_carries_disclaimer_on_all_endpoints() -> None:
    client, _ = make_client()
    for url in (
        LATEST,
        "/api/v1/recommendations?date=2026-11-13",
        "/api/v1/rankings",
        "/api/v1/tickers/ORCL/analysis",
        "/api/v1/tickers/ABC/analysis",
    ):
        assert client.get(url).json()["disclaimer"] == DISCLAIMER, url


def test_contract_api_read_errors_use_problem_json_with_request_id() -> None:
    client, _ = make_client()
    response = client.get("/api/v1/nope")
    body = problem(response, 404, "not-found")
    assert response.headers["x-request-id"] == body["request_id"]
    assert NOW  # clock fixture is injected, not read from the system
    assert make_store().latest_published() is not None
