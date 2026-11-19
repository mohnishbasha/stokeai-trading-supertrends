# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Effective factor weights (Signal Engine Specification, Regime detection and dynamic weights; S3-T05)."""  # noqa: E501

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from supertrends.scoring.config import ScoringConfig
from supertrends.scoring.factor import FactorResult

__all__ = ["NoScorableFactorsError", "WeightResult", "compute_weights"]


class NoScorableFactorsError(ValueError):
    """Every factor is missing, so there is no composite."""


@dataclass(frozen=True)
class WeightResult:
    base: Mapping[str, float]
    regime_multipliers: Mapping[str, float]
    pre_normalization: Mapping[str, float]
    weights: Mapping[str, float]
    adjustments: tuple[str, ...]
    event_risk: bool


def compute_weights(
    results: Mapping[str, FactorResult],
    config: ScoringConfig,
    *,
    regime: str | None = None,
    days_to_earnings: int | None = None,
    event_risk: bool = False,
) -> WeightResult:
    raise NotImplementedError("S3-T05")
