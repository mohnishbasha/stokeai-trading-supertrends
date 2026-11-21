# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""In-memory read store and app fixture helpers for the read API contract tests (S3-T09)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from supertrends.api import deps
from supertrends.api.app import create_app
from supertrends.runs.reads import (
    AnalysisRows,
    BarRow,
    BarsData,
    FactorRow,
    PickExtras,
    RankingPage,
    RankingRow,
    ScoreRow,
    SupersededRun,
    TickerInfo,
)
from supertrends.runs.service import (
    NarrativeView,
    RecommendationView,
    RunView,
    TransitionView,
    TriggerResult,
)
from supertrends.scoring.config import FACTOR_IDS, ScoringConfig, load_scoring_config
from supertrends.settings import Settings

TOKEN = "contract-token"  # noqa: S105
AUTH = {"Authorization": f"Bearer {TOKEN}"}
PROBLEM = "application/problem+json"
NOW = datetime(2026, 11, 16, 22, 0, tzinfo=UTC)  # Monday after the close
TRADE_DATE = date(2026, 11, 13)
RUN_ID = "01JCX4K5M6N7P8Q9R0S1T2V3W4"
OLD_RUN_ID = "01JCW4K5M6N7P8Q9R0S1T2V3W4"
ACTIVE_ID = "01JCY4K5M6N7P8Q9R0S1T2V3W4"
HASH = "sha256:" + "a" * 64
CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"


def run_view(run_id: str = RUN_ID, **kw: Any) -> RunView:
    base: dict[str, Any] = {
        "id": run_id,
        "trade_date": TRADE_DATE,
        "state": "published",
        "trigger": "schedule",
        "config_hash": HASH,
        "code_version": "1.0.0 (abc1234)",
        "market_regime": "risk_on",
        "created_at": NOW,
        "started_at": NOW,
        "finished_at": NOW,
        "published_at": NOW,
        "superseded_by": None,
        "error_code": None,
        "error_detail": None,
        "summary": {
            "tickers_total": 4,
            "tickers_scored": 3,
            "tickers_excluded": 1,
            "excluded": [{"ticker": "ABC", "reason": "stale"}],
            "buys": ["ORCL"],
            "sells": [],
            "also_qualified": [
                {"ticker": "VOO", "side": "buy", "duplicates": "ORCL", "correlation": 0.99}
            ],
            "nearest_miss": {
                "buy": None,
                "sell": {
                    "ticker": "XYZ",
                    "display_score": 37.2,
                    "threshold": 35.0,
                    "reason": "score above the sell threshold of 35",
                },
            },
            "narrative_llm": 0,
            "narrative_template": 1,
            "duration_seconds": 12.5,
        },
        "transitions": (
            TransitionView(1, None, "queued", NOW, {}),
            TransitionView(2, "queued", "ingesting", NOW, {}),
        ),
    }
    base.update(kw)
    return RunView(**base)


def pick_view(symbol: str = "ORCL", side: str = "buy") -> RecommendationView:
    evidence = {
        "supertrend": {"dir_d": 1, "dir_w": 1, "bars_since_flip": 3, "line": 212.4},
        "regime": "trending",
        "flags": [],
        "days_on_list": 1,
        "invalidation": {"level": 212.4, "rule": "daily close below the Supertrend line"},
        "factors": [
            {"id": "supertrend", "contribution": 23.4},
            {"id": "macd", "contribution": 9.1},
            {"id": "sma", "contribution": -12.0},
            {"id": "volume_osc", "contribution": 1.0},
        ],
        "ripster": {"bias": 1, "stack": 1},
    }
    return RecommendationView(
        id="01JCZ4K5M6N7P8Q9R0S1T2V3W4",
        run_id=RUN_ID,
        symbol=symbol,
        trade_date=TRADE_DATE,
        side=side,
        rank=1,
        display_score=78.4,
        confidence=71.0,
        band="Buy",
        evidence=evidence,
        narrative=NarrativeView("Daily Supertrend is up.", "template", None, "tmpl-1"),
        entry_price=None,
        entry_date=None,
    )


def score_row(**kw: Any) -> ScoreRow:
    base: dict[str, Any] = {
        "status": "scored",
        "exclusion_reason": None,
        "data_quality": "ok",
        "composite": 56.8,
        "display_score": 78.4,
        "band": "Buy",
        "confidence": 71.0,
        "regime": "trending",
        "st_dir_d": 1,
        "st_dir_w": 1,
        "bars_since_flip": 3,
        "st_line": 212.4,
        "buy_threshold": 65.0,
        "sell_threshold": 30.0,
        "candidate": "buy",
        "weights": {fid: {"base": 8.0, "final": 8.5} for fid in FACTOR_IDS},
        "adjustments": ["trending regime"],
        "flags": [],
    }
    base.update(kw)
    return ScoreRow(**base)


SNAPSHOT: dict[str, Any] = {
    "daily": {
        "close": 223.5,
        "atr": 4.1,
        "distance_atr": 1.2,
        "supertrend": {"line": 212.4, "direction": 1.0},
        "bars_since_flip": 3.0,
    },
    "weekly": {"supertrend_direction": 1.0},
    "levels": {"support_resistance": {"supports": [], "resistances": []}},
    "fib": {"retracements": [], "extensions": []},
    "ripster": {
        "bias": 1.0,
        "stack": 1.0,
        "bars_since_stack_flip": 12.0,
        "c2_dir": 1.0,
        "c3_dir": 1.0,
        "c3_top": 210.8,
        "c3_bot": 206.3,
        "dir_w": 1.0,
    },
}


@dataclass
class FakeStore:
    """Dict-backed `ReadStore`. Mutate the attributes in a test to set up a scenario."""

    runs: dict[str, RunView] = field(default_factory=dict)
    published: dict[date, RunView] = field(default_factory=dict)
    picks_by_run: dict[str, list[RecommendationView]] = field(default_factory=dict)
    superseded: dict[date, list[SupersededRun]] = field(default_factory=dict)
    tickers: dict[str, TickerInfo] = field(default_factory=dict)
    analysis_by_key: dict[tuple[str, str], AnalysisRows] = field(default_factory=dict)
    rankings_by_run: dict[str, RankingPage] = field(default_factory=dict)
    groups: set[str] = field(default_factory=set)
    bar_rows: list[BarRow] = field(default_factory=list)
    trigger_result: TriggerResult | None = None
    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def latest_published(self) -> RunView | None:
        if not self.published:
            return None
        return self.published[max(self.published)]

    def published_for_date(self, trade_date: date) -> RunView | None:
        return self.published.get(trade_date)

    def superseded_for_date(self, trade_date: date) -> list[SupersededRun]:
        return self.superseded.get(trade_date, [])

    def picks(self, run_id: str) -> list[RecommendationView]:
        return self.picks_by_run.get(run_id, [])

    def pick_extras(
        self, run_id: str, picked: Sequence[str], others: Sequence[str]
    ) -> PickExtras:
        return PickExtras(
            expected_move={s: 4.1 for s in picked},
            ribbon={s: "UUUUDDDUUU" for s in picked},
            scores={s: (77.9, 70.0) for s in others},
        )

    def rankings(
        self, run_id: str, limit: int, offset: int, group: str | None
    ) -> RankingPage | None:
        if group is not None and group not in self.groups:
            return None
        page = self.rankings_by_run.get(run_id, RankingPage(0, []))
        return RankingPage(page.total, page.rows[offset : offset + limit])

    def ticker(self, symbol: str) -> TickerInfo | None:
        return self.tickers.get(symbol)

    def analysis_rows(self, run_id: str, symbol: str) -> AnalysisRows | None:
        return self.analysis_by_key.get((run_id, symbol))

    def latest_bar_date(self, symbol: str, tf: str) -> date | None:
        return self.bar_rows[-1].t if self.bar_rows else None

    def bars(self, symbol: str, tf: str, start: date, end: date) -> BarsData:
        self.calls.append(("bars", symbol, tf, start, end))
        rows = [b for b in self.bar_rows if start <= b.t <= end]
        overlays = {
            "supertrend": [{"t": b.t.isoformat(), "value": b.c - 1.0, "dir": 1} for b in rows],
            "sma_20": [],
            "sma_50": [],
            "sma_200": [],
            "ripster_c2": [],
            "ripster_c3": [],
        }
        return BarsData(rows, overlays)

    def list_runs(self, limit: int, before: str | None) -> list[RunView]:
        self.calls.append(("list_runs", limit, before))
        ordered = sorted(self.runs.values(), key=lambda r: r.id, reverse=True)
        if before is not None:
            ordered = [r for r in ordered if r.id < before]
        return [self._list_view(r) for r in ordered[:limit]]

    @staticmethod
    def _list_view(run: RunView) -> RunView:
        return RunView(**{**run.__dict__, "transitions": ()})

    def get_run(self, run_id: str) -> RunView | None:
        return self.runs.get(run_id)

    def trigger(self, config: ScoringConfig, trade_date: date) -> TriggerResult:
        self.calls.append(("trigger", trade_date))
        return self.trigger_result or TriggerResult("queued", trade_date, run_id=RUN_ID)


def make_store() -> FakeStore:
    store = FakeStore()
    run = run_view()
    old = run_view(OLD_RUN_ID, superseded_by=RUN_ID)
    store.runs = {RUN_ID: run, OLD_RUN_ID: old}
    store.published = {TRADE_DATE: run}
    store.picks_by_run = {RUN_ID: [pick_view()]}
    store.superseded = {TRADE_DATE: [SupersededRun(OLD_RUN_ID, NOW)]}
    store.tickers = {
        "ORCL": TickerInfo("ORCL", "Oracle Corp"),
        "ABC": TickerInfo("ABC", "Abc Inc"),
        "SPY": TickerInfo("SPY", "SPDR S&P 500"),
    }
    factors = [
        FactorRow(fid, 100.0, 8.0, 8.5, "ok", [{"reason": f"{fid} reason"}]) for fid in FACTOR_IDS
    ]
    store.analysis_by_key = {
        (RUN_ID, "ORCL"): AnalysisRows(score_row(), factors, SNAPSHOT),
        (RUN_ID, "ABC"): AnalysisRows(
            score_row(
                status="excluded",
                exclusion_reason="stale",
                data_quality="stale",
                composite=None,
                display_score=None,
                band=None,
                confidence=None,
                regime=None,
                candidate=None,
                weights=None,
                adjustments=[],
            ),
            [],
            None,
        ),
    }
    store.groups = {"ai-infra"}
    store.rankings_by_run = {
        RUN_ID: RankingPage(
            3,
            [
                RankingRow(1, "ORCL", 78.4, "Buy", 71.0, 56.8, "trending", 1, 1, 3, "buy", [], []),
                RankingRow(2, "VOO", 77.9, "Buy", 70.0, 55.0, "trending", 1, 1, 9, "buy", [], []),
                RankingRow(3, "NVDA", 50.0, "Neutral", 40.0, 0.0, "ranging", 1, 1, 9, None, [], []),
            ],
        )
    }
    store.bar_rows = [
        BarRow(date(2026, 11, d), 220.1, 224.0, 219.2, 223.5, 9123000) for d in (11, 12, 13)
    ]
    return store


def make_client(store: FakeStore | None = None) -> tuple[TestClient, FakeStore]:
    store = store or make_store()
    app = create_app(settings=Settings(api_token=TOKEN))  # type: ignore[arg-type]
    cfg = load_scoring_config(CONFIG_PATH)
    app.dependency_overrides[deps.get_store] = lambda: store
    app.dependency_overrides[deps.get_clock] = lambda: NOW
    app.dependency_overrides[deps.get_scoring_config] = lambda: cfg
    return TestClient(app, base_url="http://localhost"), store


def problem(response: Any, status: int, slug: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith(PROBLEM)
    body: dict[str, Any] = response.json()
    assert body["type"] == f"urn:supertrends:problem:{slug}"
    assert body["status"] == status
    assert body["request_id"]
    return body
