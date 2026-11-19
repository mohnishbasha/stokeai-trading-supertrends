# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Confidence (Signal Engine Specification, Composite score, confidence, and bands; FR-327; S3-T05)."""  # noqa: E501

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from supertrends.scoring.config import ScoringConfig
from supertrends.scoring.factor import FactorResult

__all__ = ["Confidence", "ConfidenceDeduction", "compute_confidence"]


@dataclass(frozen=True)
class ConfidenceDeduction:
    code: str
    points: float
    reason: str


@dataclass(frozen=True)
class Confidence:
    value: float
    agreement: float
    deductions: tuple[ConfidenceDeduction, ...]


def compute_confidence(  # noqa: PLR0913
    snapshot: Mapping[str, Any],
    results: Mapping[str, FactorResult],
    weights: Mapping[str, float],
    composite: float,
    config: ScoringConfig,
    *,
    event_risk: bool = False,
) -> Confidence:
    raise NotImplementedError("S3-T05")
