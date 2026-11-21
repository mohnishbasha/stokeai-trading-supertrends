# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Read API against real Postgres: `PgStore` queries behind every endpoint (S3-T09).

Runs only when SUPERTRENDS_IT_DATABASE_URL is set. Each test migrates in its own fixture and
downgrades to base afterwards.
"""

from __future__ import annotations

import math
import os
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from supertrends.api import deps
from supertrends.api.app import create_app
from supertrends.data import db
from supertrends.data.models import (
    BarDaily,
    BarIntraday,
    FactorScore,
    IndicatorSnapshot,
    Narrative,
    Recommendation,
    Run,
    Ticker,
    TickerScore,
    Watchlist,
    WatchlistGroup,
    WatchlistGroupMember,
    WatchlistItem,
)
from supertrends.runs.narrator import DISCLAIMER
from supertrends.runs.repo import ensure_config_version
from supertrends.scoring.config import FACTOR_IDS, load_scoring_config
from supertrends.settings import Settings

URL = os.environ.get("SUPERTRENDS_IT_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="set SUPERTRENDS_IT_DATABASE_URL to run")

TOKEN = "it-token"  # noqa: S105
AUTH = {"Authorization": f"Bearer {TOKEN}"}
NOW = datetime(2026, 11, 16, 22, 0, tzinfo=UTC)
TRADE_DATE = date(2026, 11, 13)
RUN_ID = "01JCX4K5M6N7P8Q9R0S1T2V3W4"
OLD_ID = "01JCW4K5M6N7P8Q9R0S1T2V3W4"
REC_ID = "01JCZ4K5M6N7P8Q9R0S1T2V3W4"
CONFIG = Path(__file__).resolve().parents[2] / "config" / "scoring.yaml"


def _downgrade(engine: Engine) -> None:
    config = db.alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")


def _sessions(engine: Engine) -> sessionmaker:  # type: ignore[type-arg]
    return sessionmaker(bind=engine, expire_on_commit=False)


def _weekdays(end: date, count: int) -> list[date]:
    days: list[date] = []
    day = end
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return days[::-1]


def _seed(engine: Engine) -> None:
    cfg = load_scoring_config(CONFIG)
    with _sessions(engine)() as s, s.begin():
        digest = ensure_config_version(s, cfg)
        for sym, name in (
            ("ORCL", "Oracle"),
            ("VOO", "Vanguard S&P"),
            ("ABC", "Abc"),
            ("QQQ", "Q"),
        ):
            s.add(Ticker(symbol=sym, name=name))
        s.flush()
        wl = Watchlist(name="default", is_default=True)
        s.add(wl)
        s.flush()
        for sym in ("ORCL", "VOO", "ABC"):
            s.add(WatchlistItem(watchlist_id=wl.id, symbol=sym, source="seed"))
        group = WatchlistGroup(watchlist_id=wl.id, slug="ai-infra", name="AI infra", position=0)
        s.add(group)
        s.flush()
        s.add(WatchlistGroupMember(group_id=group.id, watchlist_id=wl.id, symbol="ORCL"))
        summary = {
            "tickers_total": 3,
            "tickers_scored": 2,
            "tickers_excluded": 1,
            "excluded": [{"ticker": "ABC", "reason": "stale"}],
            "buys": ["ORCL"],
            "sells": [],
            "also_qualified": [
                {"ticker": "VOO", "side": "buy", "duplicates": "ORCL", "correlation": 0.99}
            ],
            "nearest_miss": {"buy": None, "sell": None},
            "narrative_llm": 0,
            "narrative_template": 1,
            "duration_seconds": 3.5,
        }
        s.add(
            Run(
                id=OLD_ID,
                trade_date=TRADE_DATE,
                state="published",
                trigger="schedule",
                config_hash=digest,
                code_version="t",
                published_at=NOW - timedelta(hours=1),
                summary={},
            )
        )
        s.flush()
        s.add(
            Run(
                id=RUN_ID,
                trade_date=TRADE_DATE,
                state="narrating",
                trigger="schedule",
                config_hash=digest,
                code_version="t",
            )
        )
        s.flush()
        s.execute(Run.__table__.update().where(Run.id == OLD_ID).values(superseded_by=RUN_ID))
        s.execute(
            Run.__table__.update()
            .where(Run.id == RUN_ID)
            .values(state="published", published_at=NOW, market_regime="risk_on", summary=summary)
        )
        for rank, (sym, score) in enumerate((("ORCL", 78.4), ("VOO", 77.9)), start=1):
            s.add(
                TickerScore(
                    run_id=RUN_ID,
                    symbol=sym,
                    status="scored",
                    data_quality="ok",
                    composite=56.8,
                    display_score=score,
                    band="Buy",
                    confidence=71.0,
                    regime="trending",
                    st_dir_d=1,
                    st_dir_w=1,
                    bars_since_flip=3,
                    st_line=212.4,
                    buy_threshold=65,
                    sell_threshold=30,
                    candidate="buy",
                    rank_overall=rank,
                    weights={f: {"base": 8.0, "final": 8.5} for f in FACTOR_IDS},
                )
            )
        s.add(
            TickerScore(
                run_id=RUN_ID,
                symbol="ABC",
                status="excluded",
                exclusion_reason="stale",
                data_quality="stale",
            )
        )
        s.flush()
        for fid in FACTOR_IDS:
            s.add(
                FactorScore(
                    run_id=RUN_ID,
                    symbol="ORCL",
                    factor_id=fid,
                    score=50.0,
                    weight=8.5,
                    contribution=4.0,
                    quality="ok",
                    evidence={"items": [{"name": "x", "reason": f"{fid} reason"}]},
                )
            )
        s.add(
            IndicatorSnapshot(
                run_id=RUN_ID,
                symbol="ORCL",
                values={
                    "daily": {"atr": 4.123, "distance_atr": 1.2},
                    "ripster": {"bias": 1.0, "c3_top": 210.8},
                },
            )
        )
        s.add(
            Recommendation(
                id=REC_ID,
                run_id=RUN_ID,
                symbol="ORCL",
                trade_date=TRADE_DATE,
                side="buy",
                rank=1,
                display_score=78.4,
                confidence=71.0,
                band="Buy",
                evidence={
                    "supertrend": {"dir_d": 1, "dir_w": 1, "bars_since_flip": 3, "line": 212.4},
                    "regime": "trending",
                    "flags": [],
                    "invalidation": {"level": 212.4, "rule": "close below the line"},
                    "factors": [{"id": "supertrend", "contribution": 23.4}],
                },
            )
        )
        s.flush()
        s.add(
            Narrative(recommendation_id=REC_ID, text="Up.", source="template", prompt_version="t1")
        )
        for i, day in enumerate(_weekdays(TRADE_DATE, 320)):
            price = 100.0 + i * 0.3 + 5 * math.sin(i / 7)
            s.add(
                BarDaily(
                    symbol="ORCL",
                    date=day,
                    open=price,
                    high=price + 2,
                    low=price - 2,
                    close=price + 1,
                    volume=1_000_000 + i,
                    provider="t",
                )
            )
        s.flush()
        s.add(
            BarIntraday(
                symbol="ORCL",
                ts=datetime(2026, 11, 13, 14, 30, tzinfo=UTC),
                open=1.0,
                high=2.0,
                low=0.5,
                close=1.5,
                volume=10,
                provider="t",
            )
        )


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = db.create_db_engine(url=URL)
    _downgrade(eng)
    db.migrate(eng)
    _seed(eng)
    yield eng
    _downgrade(eng)
    eng.dispose()


@pytest.fixture
def client(engine: Engine) -> TestClient:
    app = create_app(settings=Settings(api_token=TOKEN, scoring_config=str(CONFIG)))  # type: ignore[arg-type]
    app.state.engine = engine
    app.dependency_overrides[deps.get_clock] = lambda: NOW
    return TestClient(app, base_url="http://localhost")


def test_it_latest_recommendations_from_postgres(client: TestClient) -> None:
    body = client.get("/api/v1/recommendations/latest").json()
    assert body["run_id"] == RUN_ID
    assert body["disclaimer"] == DISCLAIMER
    pick = body["buys"][0]
    assert pick["ticker"] == "ORCL"
    assert pick["recommendation_id"] == REC_ID
    assert pick["expected_1d_move"] == 4.12
    assert set(pick["ribbon"]) <= {"U", "D"}
    assert len(pick["ribbon"]) == 10
    assert pick["narrative"]["source"] == "template"
    assert body["also_qualified"][0]["ticker"] == "VOO"
    assert body["also_qualified"][0]["display_score"] == 77.9
    assert [s["id"] for s in body["superseded_runs"]] == [OLD_ID]
    assert body["config"]["version"] >= 1
    by_date = client.get("/api/v1/recommendations", params={"date": "2026-11-13"}).json()
    assert by_date["run_id"] == RUN_ID
    assert client.get("/api/v1/recommendations", params={"date": "2026-11-12"}).status_code == 404


def test_it_rankings_groups_and_paging(client: TestClient) -> None:
    body = client.get("/api/v1/rankings").json()
    assert [i["ticker"] for i in body["items"]] == ["ORCL", "VOO"]
    assert [i["picked"] for i in body["items"]] == ["buy", "also_qualified"]
    assert body["items"][0]["groups"] == ["ai-infra"]
    assert body["total"] == 2
    grouped = client.get("/api/v1/rankings?group=ai-infra").json()
    assert [i["ticker"] for i in grouped["items"]] == ["ORCL"]
    assert grouped["total"] == 1
    assert client.get("/api/v1/rankings?group=nope").status_code == 404
    paged = client.get("/api/v1/rankings?limit=1&offset=1").json()
    assert [i["ticker"] for i in paged["items"]] == ["VOO"]


def test_it_ticker_analysis_scored_excluded_and_unknown(client: TestClient) -> None:
    body = client.get("/api/v1/tickers/ORCL/analysis").json()
    assert [f["id"] for f in body["factors"]] == list(FACTOR_IDS)
    assert body["factors"][0]["reasons"] == [f"{FACTOR_IDS[0]} reason"]
    assert body["expected_1d_move"] == 4.12
    assert body["ripster"]["c3_top"] == 210.8
    assert body["picked"]["recommendation_id"] == REC_ID
    excluded = client.get("/api/v1/tickers/ABC/analysis").json()
    assert (excluded["status"], excluded["exclusion_reason"]) == ("excluded", "stale")
    absent = client.get("/api/v1/tickers/QQQ/analysis")
    assert absent.status_code == 404
    unknown = client.get("/api/v1/tickers/ZZZZ/analysis")
    assert unknown.json()["type"].endswith("ticker-not-found")


def test_it_bars_daily_weekly_intraday_with_overlays(client: TestClient) -> None:
    daily = client.get("/api/v1/tickers/ORCL/bars").json()
    assert daily["to"] == "2026-11-13"
    assert len(daily["bars"]) > 200
    assert daily["overlays"]["sma_20"]
    assert {"top", "bot", "dir"} <= set(daily["overlays"]["ripster_c3"][-1])
    assert daily["overlays"]["supertrend"][-1]["dir"] in (1, -1)
    weekly = client.get("/api/v1/tickers/ORCL/bars?tf=1w&from=2026-01-01").json()
    assert 40 < len(weekly["bars"]) < 60
    ranged = client.get("/api/v1/tickers/ORCL/bars?from=2026-11-10&to=2026-11-13").json()
    assert [b["t"] for b in ranged["bars"]] == [
        "2026-11-10",
        "2026-11-11",
        "2026-11-12",
        "2026-11-13",
    ]
    intraday = client.get("/api/v1/tickers/ORCL/bars?tf=5m").json()
    assert intraday["bars"][0]["t"] == "2026-11-13T14:30:00Z"
    voo = client.get("/api/v1/tickers/VOO/bars").json()
    assert voo["bars"] == []


def test_it_runs_list_detail_and_trigger(client: TestClient) -> None:
    listing = client.get("/api/v1/runs").json()
    assert [r["id"] for r in listing["items"]] == [RUN_ID, OLD_ID]
    detail = client.get(f"/api/v1/runs/{RUN_ID}").json()
    assert detail["transitions"] == []
    assert detail["summary"]["narrative"] == {"llm": 0, "template": 1}
    queued = client.post("/api/v1/runs", json={"date": "2026-11-13"}, headers=AUTH)
    assert queued.status_code == 202
    new_id = queued.json()["run_id"]
    assert client.get(f"/api/v1/runs/{new_id}").json()["state"] == "queued"
    again = client.post("/api/v1/runs", json={"date": "2026-11-13"}, headers=AUTH)
    assert again.status_code == 409
    assert again.json()["active_run_id"] == new_id


def test_it_config_scoring(client: TestClient) -> None:
    body = client.get("/api/v1/config/scoring").json()
    assert body["hash"].startswith("sha256:")
