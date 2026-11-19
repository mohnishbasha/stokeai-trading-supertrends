# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Per-ticker regime from ADX (Signal Engine Specification, Regime detection; FR-317; S3-T05)."""

from __future__ import annotations

from collections.abc import Mapping

from supertrends.scoring.config import ScoringConfig

__all__ = ["classify_regime", "regime_multipliers"]


def classify_regime(adx: float | None, config: ScoringConfig) -> str:
    raise NotImplementedError("S3-T05")


def regime_multipliers(regime: str | None, config: ScoringConfig) -> Mapping[str, float]:
    raise NotImplementedError("S3-T05")
