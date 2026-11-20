# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Composite, display score, bands and the score card (FR-324 to FR-328; S3-T05).

```
composite = sum(w_i * s_i) / sum(w_i)        over factors with quality != missing, -100..100
display   = round((composite + 100) / 2, 1) 0..100 (Python round: half to even on the double)
contribution_i = w_i * s_i / 100             so the contributions sum to the composite
```

Bands on the display score: 80 to 100 Strong Buy; `thresholds.buy_display_min` (65) to 79.9 Buy;
50 to 64.9 Neutral, leaning up; 35.1 to 49.9 Neutral, leaning down; 20.1 to
`thresholds.sell_display_max` (35) Sell; 0 to 20 Strong Sell. The 80, 50 and 20 edges have no key
in the config (PRD A-32).

`score_ticker` is the one entry point the selection, orchestrator and evidence tasks use: it takes
the indicator snapshot, the factor results by ID and the factor context, and returns a frozen
`ScoreCard`. Pure: no I/O, clock or randomness; it never reads LLM output.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from supertrends.scoring.confidence import ConfidenceDeduction, compute_confidence
from supertrends.scoring.config import FACTOR_IDS, WEIGHT_SUM, ScoringConfig
from supertrends.scoring.factor import (
    REGIME_INPUT_PATHS,
    FactorContext,
    FactorResult,
    Quality,
    get_path,
)
from supertrends.scoring.regime import classify_regime
from supertrends.scoring.weights import WeightResult, compute_weights, freeze_mapping

__all__ = [
    "Band",
    "Composite",
    "ScoreCard",
    "assign_band",
    "compute_composite",
    "display_score",
    "score_ticker",
]

STRONG_BUY_MIN = 80.0
NEUTRAL_UP_MIN = 50.0
STRONG_SELL_MAX = 20.0
WEIGHT_SUM_TOLERANCE = 1e-6


class Band(StrEnum):
    """Display band, best to worst (FR-326). Values are the labels shown to users."""

    STRONG_BUY = "Strong Buy"
    BUY = "Buy"
    NEUTRAL_UP = "Neutral, leaning up"
    NEUTRAL_DOWN = "Neutral, leaning down"
    SELL = "Sell"
    STRONG_SELL = "Strong Sell"


@dataclass(frozen=True)
class Composite:
    """The composite (-100..100) and each factor's contribution; missing factors contribute 0."""

    composite: float
    contributions: Mapping[str, float]


@dataclass(frozen=True)
class ScoreCard:
    """Everything the scoring engine concludes about one ticker on one date.

    All mappings are read-only and keyed by factor ID in `FACTOR_IDS` order.

    * `composite`: -100..100; `display_score`: 0..100 (one decimal); `band`: from the display score.
    * `confidence`: 0..100, not rounded; `agreement`: 0..1; `deductions`: what lowered it.
    * `contributions`: `weight * score / 100` per factor; they sum to `composite` within 1e-9.
    * `weights`: effective weights (0 for missing, summing to 100); `weight_detail`: base, regime
      multipliers and pre-normalization weights behind them.
    * `scores` and `qualities`: each factor's score and quality, so a table needs no second input.
    * `regime`: the ADX regime of the ticker (informational); `regime_applied`: the regime whose
      multipliers were used (`None` while none is injected, the Sprint 3 run).
    * `event_risk`: earnings within the window or injected; `adjustments`: every weight
      adjustment that fired, as display text.
    """

    composite: float
    display_score: float
    band: Band
    confidence: float
    agreement: float
    deductions: tuple[ConfidenceDeduction, ...]
    contributions: Mapping[str, float]
    weights: Mapping[str, float]
    weight_detail: WeightResult
    scores: Mapping[str, float]
    qualities: Mapping[str, Quality]
    regime: str
    regime_applied: str | None
    event_risk: bool
    adjustments: tuple[str, ...]


def compute_composite(
    results: Mapping[str, FactorResult], weights: Mapping[str, float]
) -> Composite:
    """Weighted composite. `weights` are effective weights (missing factors weigh 0, rest sum 100).

    Raises ValueError if the non-missing weights do not sum to 100.
    """
    total = math.fsum(weights[fid] for fid in FACTOR_IDS if not results[fid].is_missing)
    if abs(total - WEIGHT_SUM) > WEIGHT_SUM_TOLERANCE:
        msg = f"effective weights of scored factors must sum to {WEIGHT_SUM:g}, got {total:g}"
        raise ValueError(msg)
    contributions = {
        fid: 0.0 if results[fid].is_missing else weights[fid] * results[fid].score / 100.0
        for fid in FACTOR_IDS
    }
    composite = math.fsum(contributions.values())
    return Composite(
        composite=min(100.0, max(-100.0, composite)), contributions=freeze_mapping(contributions)
    )


def display_score(composite: float) -> float:
    """`round((composite + 100) / 2, 1)`, kept inside 0..100."""
    return min(100.0, max(0.0, round((composite + 100.0) / 2.0, 1)))


def assign_band(display: float, config: ScoringConfig) -> Band:
    """The band of a display score (FR-326)."""
    if display >= STRONG_BUY_MIN:
        return Band.STRONG_BUY
    if display >= config.thresholds.buy_display_min:
        return Band.BUY
    if display >= NEUTRAL_UP_MIN:
        return Band.NEUTRAL_UP
    if display > config.thresholds.sell_display_max:
        return Band.NEUTRAL_DOWN
    if display > STRONG_SELL_MAX:
        return Band.SELL
    return Band.STRONG_SELL


def score_ticker(
    snapshot: Mapping[str, Any],
    results: Mapping[str, FactorResult],
    context: FactorContext,
) -> ScoreCard:
    """Score one ticker from its snapshot, its twelve factor results and the factor context.

    The weights apply `context.regime` (none in Sprint 3), `context.days_to_earnings` and
    `context.event_risk`. Raises ValueError if `results` is not exactly one result per factor,
    NoScorableFactorsError if all are missing, KeyError for a snapshot path that is absent.
    """
    config = context.config
    detail = compute_weights(
        results,
        config,
        regime=context.regime,
        days_to_earnings=context.days_to_earnings,
        event_risk=context.event_risk,
    )
    comp = compute_composite(results, detail.weights)
    display = display_score(comp.composite)
    conf = compute_confidence(
        snapshot, results, detail.weights, comp.composite, config, event_risk=detail.event_risk
    )
    adx = get_path(snapshot, REGIME_INPUT_PATHS[0])
    return ScoreCard(
        composite=comp.composite,
        display_score=display,
        band=assign_band(display, config),
        confidence=conf.value,
        agreement=conf.agreement,
        deductions=conf.deductions,
        contributions=comp.contributions,
        weights=detail.weights,
        weight_detail=detail,
        scores=freeze_mapping({fid: results[fid].score for fid in FACTOR_IDS}),
        qualities=MappingProxyType({fid: results[fid].quality for fid in FACTOR_IDS}),
        regime=classify_regime(adx, config),
        regime_applied=context.regime,
        event_risk=detail.event_risk,
        adjustments=detail.adjustments,
    )
