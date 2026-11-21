# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Per-ticker regime from ADX (Signal Engine Specification, Regime detection; FR-317; S3-T05).

`classify_regime` turns the daily ADX into `trending` (ADX >= `regime.trending_min`), `ranging`
(ADX < `regime.ranging_max`) or `transitional`. `regime_multipliers` returns the multiplier of
every factor for a regime from `regime.multipliers`; `None` (no regime injected, the Sprint 3
run) and `transitional` give 1.0 for every factor. Both are pure and read only the config.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType

from supertrends.scoring.config import FACTOR_IDS, REGIMES, ScoringConfig

__all__ = ["classify_regime", "regime_multipliers"]

TRENDING = "trending"
RANGING = "ranging"
TRANSITIONAL = "transitional"


def classify_regime(adx: float | None, config: ScoringConfig) -> str:
    """The regime for a daily ADX. A null or NaN ADX (warm-up) is `transitional`: no tilt."""
    if adx is None or math.isnan(adx):
        return TRANSITIONAL
    if adx >= config.regime.trending_min:
        return TRENDING
    if adx < config.regime.ranging_max:
        return RANGING
    return TRANSITIONAL


def regime_multipliers(regime: str | None, config: ScoringConfig) -> Mapping[str, float]:
    """Multiplier per factor ID for `regime`; `None` means no regime and is all 1.0."""
    if regime is None:
        return MappingProxyType(dict.fromkeys(FACTOR_IDS, 1.0))
    if regime not in REGIMES:
        msg = f"unknown regime {regime!r}; expected one of {list(REGIMES)}"
        raise ValueError(msg)
    table = config.regime.multipliers[regime]
    return MappingProxyType({fid: float(table[fid]) for fid in FACTOR_IDS})
