# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Composite, display score, bands, and the score card (Signal Engine Specification; FR-324 to FR-328; S3-T05)."""  # noqa: E501

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from supertrends.scoring.confidence import ConfidenceDeduction
from supertrends.scoring.config import ScoringConfig
from supertrends.scoring.factor import FactorContext, FactorResult, Quality
from supertrends.scoring.weights import WeightResult

__all__ = [
    "Band",
    "Composite",
    "ScoreCard",
    "assign_band",
    "compute_composite",
    "display_score",
    "score_ticker",
]


class Band(StrEnum):
    STRONG_BUY = "Strong Buy"
    BUY = "Buy"
    NEUTRAL_UP = "Neutral, leaning up"
    NEUTRAL_DOWN = "Neutral, leaning down"
    SELL = "Sell"
    STRONG_SELL = "Strong Sell"


@dataclass(frozen=True)
class Composite:
    composite: float
    contributions: Mapping[str, float]


@dataclass(frozen=True)
class ScoreCard:
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
    raise NotImplementedError("S3-T05")


def display_score(composite: float) -> float:
    raise NotImplementedError("S3-T05")


def assign_band(display: float, config: ScoringConfig) -> Band:
    raise NotImplementedError("S3-T05")


def score_ticker(
    snapshot: Mapping[str, Any],
    results: Mapping[str, FactorResult],
    context: FactorContext,
) -> ScoreCard:
    raise NotImplementedError("S3-T05")
