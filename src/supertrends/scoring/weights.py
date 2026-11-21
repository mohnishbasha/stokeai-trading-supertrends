# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Effective factor weights (Signal Engine Specification, dynamic weights; FR-316 to FR-319).

Order of operations (FR-316 to FR-319, FR-324; ADR-038, ADR-064):

1. base weights from `weights` in the scoring config (sum 100);
2. times the regime multiplier (1.0 when no regime is injected, as in the Sprint 3 run);
3. fundamentals times `events.earnings_fundamentals_multiplier` when earnings are within
   `events.earnings_window_days` (and `event_risk` is set);
4. times each result's `weight_multiplier` (0.6 flow daily estimate, 0.5 stale fundamentals);
5. `missing` factors drop to 0 and the rest are renormalized proportionally to sum 100.

Every adjustment that fired is returned as text for the stored result and the UI (FR-323).
Pure: no I/O, clock or randomness.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from supertrends.scoring.config import FACTOR_IDS, WEIGHT_SUM, ScoringConfig
from supertrends.scoring.factor import FactorResult, Quality, format_number
from supertrends.scoring.regime import regime_multipliers

__all__ = ["NoScorableFactorsError", "WeightResult", "compute_weights", "freeze_mapping"]


class NoScorableFactorsError(ValueError):
    """Every factor is missing (or has no weight), so there is no composite."""


def freeze_mapping(data: Mapping[str, float]) -> Mapping[str, float]:
    """A read-only copy of `data`."""
    return MappingProxyType(dict(data))


@dataclass(frozen=True)
class WeightResult:
    """The weights of one ticker and how they were reached. Mappings are keyed by factor ID.

    `weights` are the effective weights: 0 for missing factors, summing to 100 otherwise.
    `pre_normalization` is base x regime x event x quality (0 for missing), before step 5.
    `adjustments` lists what fired, e.g. `("trending regime", "earnings in 3 days")`.
    """

    base: Mapping[str, float]
    regime_multipliers: Mapping[str, float]
    pre_normalization: Mapping[str, float]
    weights: Mapping[str, float]
    adjustments: tuple[str, ...]
    event_risk: bool


def _check_coverage(results: Mapping[str, FactorResult]) -> None:
    unknown = sorted(set(results) - set(FACTOR_IDS))
    absent = [fid for fid in FACTOR_IDS if fid not in results]
    if unknown or absent:
        msg = f"results must cover exactly the factor ids; unknown {unknown}, absent {absent}"
        raise ValueError(msg)
    for fid, result in results.items():
        if result.factor_id != fid:
            msg = f"result under key {fid!r} is for factor {result.factor_id!r}"
            raise ValueError(msg)


def _earnings_text(days: int) -> str:
    return f"earnings in {days} day" + ("" if days == 1 else "s")


def compute_weights(
    results: Mapping[str, FactorResult],
    config: ScoringConfig,
    *,
    regime: str | None = None,
    days_to_earnings: int | None = None,
    event_risk: bool = False,
) -> WeightResult:
    """Effective weights for one ticker. Raises ValueError on a bad results mapping and
    NoScorableFactorsError when no factor can carry weight."""
    _check_coverage(results)
    base = config.weights.as_dict()
    multipliers = regime_multipliers(regime, config)
    adjustments: list[str] = []
    if regime is not None and any(multipliers[f] != 1.0 for f in FACTOR_IDS):
        adjustments.append(f"{regime} regime")

    fund_multiplier = 1.0
    earnings_soon = (
        days_to_earnings is not None and 0 <= days_to_earnings <= config.events.earnings_window_days
    )
    if earnings_soon:
        assert days_to_earnings is not None  # noqa: S101 - narrowed by earnings_soon, for mypy
        fund_multiplier = config.events.earnings_fundamentals_multiplier
        adjustments.append(_earnings_text(days_to_earnings))

    pre: dict[str, float] = {}
    for fid in FACTOR_IDS:
        result = results[fid]
        if result.is_missing:
            pre[fid] = 0.0
            continue
        value = base[fid] * multipliers[fid]
        if fid == "fundamentals":
            value *= fund_multiplier
        value *= result.weight_multiplier
        pre[fid] = value
        if result.weight_multiplier != 1.0:
            q = result.quality.value if result.quality is not Quality.OK else "adjusted"
            adjustments.append(f"{fid} weight x{format_number(result.weight_multiplier)} ({q})")
    adjustments.extend(
        f"{fid} missing, weight redistributed" for fid in FACTOR_IDS if results[fid].is_missing
    )

    total = math.fsum(pre.values())
    if total <= 0:
        msg = "no factor can carry weight: every factor is missing or has zero weight"
        raise NoScorableFactorsError(msg)
    weights = {fid: pre[fid] * WEIGHT_SUM / total for fid in FACTOR_IDS}
    return WeightResult(
        base=freeze_mapping(base),
        regime_multipliers=multipliers,
        pre_normalization=freeze_mapping(pre),
        weights=freeze_mapping(weights),
        adjustments=tuple(adjustments),
        event_risk=event_risk or earnings_soon,
    )
