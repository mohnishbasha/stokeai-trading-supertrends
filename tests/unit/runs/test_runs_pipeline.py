# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Pure run steps on the fixture universe (TS-OPS-105 to 108; S3-T07, FR-906, NFR-002)."""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from supertrends.data.calendar import sessions_between
from supertrends.runs.narrator import DISCLAIMER, MinimalNarrator, PickContext
from supertrends.runs.pipeline import (
    ScoredTicker,
    build_summary,
    classify_universe,
    display_decimal,
    excluded_row,
    factor_score_rows,
    json_safe,
    rank_overall,
    score_one,
    ticker_score_row,
)
from supertrends.scoring.config import ScoringConfig, load_scoring_config
from supertrends.scoring.factor import FactorContext
from supertrends.scoring.factors import default_registry
from supertrends.scoring.snapshot import compute_snapshot
from supertrends.selection import Exclusion, select
from tests.golden.determinism import AS_OF, bundle_for, provider

CONFIG = Path(__file__).parents[3] / "config" / "scoring.yaml"
TICKERS = ("FXA", "FXB", "FXF", "FXG", "FXL")


@pytest.fixture(scope="module")
def cfg() -> ScoringConfig:
    return load_scoring_config(CONFIG)


@pytest.fixture(scope="module")
def snapshots(cfg: ScoringConfig) -> dict[str, dict[str, Any]]:
    fixture = provider()
    return {t: compute_snapshot(bundle_for(fixture, t), cfg, AS_OF) for t in TICKERS}


def _score(cfg: ScoringConfig, snapshots: dict[str, dict[str, Any]]) -> list[ScoredTicker]:
    factors = default_registry().ordered(cfg)
    ctx = FactorContext(config=cfg, as_of=AS_OF)
    return [score_one(t, snapshots[t], factors, ctx, "ok") for t in TICKERS]


def test_unit_runs_classify_universe_excludes_with_reasons() -> None:
    sessions = sessions_between(date(2025, 1, 1), AS_OF)
    bar_dates = {
        "OK": sessions,
        "OLD": sessions[:-3],
        "NEW": sessions[-100:],
        "NONE": [],
    }
    quality, excluded = classify_universe(
        ["OK", "OLD", "NEW", "NONE", "GONE"], bar_dates, AS_OF, unresolved=["GONE"]
    )
    assert quality["OK"] == "ok"
    assert quality["OLD"] == "stale"
    assert quality["NEW"] == "insufficient_history"
    assert [(e.ticker, e.reason) for e in excluded] == [
        ("GONE", "unresolved"),
        ("NEW", "insufficient_history"),
        ("NONE", "no_data"),
        ("OLD", "stale"),
    ]
    assert excluded_row("r", excluded[0], quality["GONE"]) == {
        "run_id": "r",
        "symbol": "GONE",
        "status": "excluded",
        "exclusion_reason": "unresolved",
        "data_quality": "insufficient_history",
    }


def test_unit_runs_pipeline_rows_are_deterministic_and_cover_every_factor(
    cfg: ScoringConfig, snapshots: dict[str, dict[str, Any]]
) -> None:
    first = _score(cfg, snapshots)
    second = _score(cfg, snapshots)
    ranks = rank_overall(first)
    assert sorted(ranks.values()) == list(range(1, len(TICKERS) + 1))
    for a, b in zip(first, second, strict=True):
        row_a = ticker_score_row("run", a, ranks[a.ticker], cfg)
        assert row_a == ticker_score_row("run", b, ranks[b.ticker], cfg)
        assert factor_score_rows("run", a) == factor_score_rows("run", b)
        assert row_a["status"] == "scored"
        assert isinstance(row_a["display_score"], Decimal)
        assert row_a["candidate"] in (None, "buy", "sell")
        assert set(row_a["weights"]) == set(cfg.weights.as_dict())
        factors = factor_score_rows("run", a)
        assert len(factors) == len(cfg.weights.as_dict())
        missing = [f for f in factors if f["quality"] == "missing"]
        assert all(f["score"] is None for f in missing)
        assert any(f["factor_id"] == "fundamentals" for f in missing)
    best = min(first, key=lambda s: ranks[s.ticker])
    assert best.card.display_score == max(s.card.display_score for s in first)


def test_unit_runs_summary_lists_exclusions_counts_and_selection(
    cfg: ScoringConfig, snapshots: dict[str, dict[str, Any]]
) -> None:
    scored = _score(cfg, snapshots)
    excluded = (Exclusion("FXZ", "stale"), Exclusion("FXY", "insufficient_history"))
    selection = select([s.entry for s in scored], {}, cfg, excluded=excluded)
    summary = build_summary(
        trade_date=AS_OF,
        config_hash="sha256:" + "0" * 64,
        scoring_version=cfg.scoring.version,
        symbols=[*TICKERS, "FXY", "FXZ"],
        scored=scored,
        excluded=excluded,
        quality={"FXA": "ok", "FXY": "insufficient_history", "FXZ": "stale"},
        provider_errors={"FXZ": ["timeout"]},
        selection=selection,
    )
    assert summary["tickers_total"] == len(TICKERS) + 2
    assert summary["tickers_scored"] == len(TICKERS)
    assert summary["tickers_excluded"] == 2
    assert summary["excluded"] == [
        {"ticker": "FXY", "reason": "insufficient_history"},
        {"ticker": "FXZ", "reason": "stale"},
    ]
    assert summary["quality_counts"] == {"insufficient_history": 1, "ok": 1, "stale": 1}
    assert summary["provider_errors"] == [{"ticker": "FXZ", "errors": ["timeout"]}]
    assert summary["buys"] == [p.ticker for p in selection.buys]
    assert summary["sells"] == [p.ticker for p in selection.sells]
    assert set(summary["nearest_miss"]) == {"buy", "sell"}
    no_selection = build_summary(
        trade_date=AS_OF,
        config_hash="h",
        scoring_version=1,
        symbols=[],
        scored=[],
        excluded=(),
        quality={},
        provider_errors={},
        selection=None,
    )
    assert "buys" not in no_selection


def test_unit_runs_minimal_narrator_evidence_carries_pick_fields_and_disclaimer(
    cfg: ScoringConfig, snapshots: dict[str, dict[str, Any]]
) -> None:
    scored = {s.ticker: s for s in _score(cfg, snapshots)}
    entries = [s.entry for s in scored.values()]
    selection = select(entries, {}, cfg)
    picks = (*selection.buys, *selection.sells)
    assert picks, "the fixture universe yields at least one pick"
    for pick in picks:
        st = scored[pick.ticker]
        ctx = PickContext(pick, AS_OF, st.snapshot, st.results, cfg)
        narrated = MinimalNarrator().narrate(ctx)
        assert narrated.narrative is None
        doc = narrated.evidence
        assert doc == MinimalNarrator().narrate(ctx).evidence
        assert doc["ticker"] == pick.ticker
        assert doc["side"] == pick.side
        assert doc["rank"] == pick.rank
        assert doc["trade_date"] == AS_OF.isoformat()
        assert doc["disclaimer"] == DISCLAIMER
        assert len(doc["factors"]) == len(cfg.weights.as_dict())
        assert len(doc["top_factors"]) == 3
        assert doc["invalidation"]["level"] == doc["supertrend"]["line"]


def test_unit_runs_json_safe_and_display_decimal() -> None:
    assert json_safe({"a": math.nan, "b": [1.0, math.inf, {"c": -math.inf}], 3: "x"}) == {
        "a": None,
        "b": [1.0, None, {"c": None}],
        "3": "x",
    }
    assert display_decimal(69.66) == Decimal("69.7")
    assert display_decimal(0.0) == Decimal("0.0")
