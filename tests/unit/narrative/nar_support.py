# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Builders for the evidence and narrative tests: real snapshots, cards and picks (S3-T08)."""

from __future__ import annotations

import json
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

from supertrends.indicators.registry import Bundle
from supertrends.scoring.composite import score_ticker
from supertrends.scoring.config import ScoringConfig, load_scoring_config
from supertrends.scoring.factor import FactorContext, FactorResult
from supertrends.scoring.factors import default_registry
from supertrends.scoring.snapshot import compute_snapshot
from supertrends.selection.candidates import SelectionInput
from supertrends.selection.ranking import Pick
from tests.unit.indicators.lookahead_support import make_bundle

CONFIG = Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"
SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "supertrends"
    / "narrative"
    / "schemas"
    / "evidence.schema.json"
)


@cache
def cfg() -> ScoringConfig:
    return load_scoring_config(CONFIG)


@cache
def bundle(seed: int, n: int = 420) -> Bundle:
    return make_bundle(seed=seed, n=n, intraday_from=n - 20)


def schema() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(SCHEMA.read_text())
    return loaded


class Scored:
    """One ticker scored from real computations."""

    def __init__(self, seed: int, t: int, side: str) -> None:
        c = cfg()
        b = bundle(seed)
        self.as_of = date.fromisoformat(str(b.dates[t]))
        self.snapshot = compute_snapshot(b, c, self.as_of)
        ctx = FactorContext(config=c, as_of=self.as_of)
        self.results: dict[str, FactorResult] = {
            f.id: f.compute(self.snapshot, ctx) for f in default_registry().ordered(c)
        }
        self.card = score_ticker(self.snapshot, self.results, ctx)
        st = self.snapshot["daily"]["supertrend"]["direction"]
        bias = self.snapshot["ripster"]["bias"]
        entry = SelectionInput(
            ticker=f"T{seed}X{t}",
            card=self.card,
            st_dir_d=None if st is None else int(st),
            rc_bias=None if bias is None else int(bias),
            bars_since_flip=self.snapshot["daily"]["bars_since_flip"],
            relative_volume=None,
            avg_dollar_volume_20d=self.snapshot["daily"]["avg_dollar_volume_20d"],
        )
        self.pick = Pick(
            rank=1,
            side="buy" if side == "buy" else "sell",
            ticker=entry.ticker,
            display_score=self.card.display_score,
            confidence=self.card.confidence,
            band=self.card.band,
            days_on_list=2,
            entry=entry,
        )


def many(seeds: range = range(1, 7), ts: tuple[int, ...] = (300, 340, 380, 419)) -> list[Scored]:
    """Scored tickers over several synthetic series, dates and both sides."""
    return [Scored(s, t, side) for s in seeds for t in ts for side in ("buy", "sell")]
