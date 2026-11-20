# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Confidence (Signal Engine Specification, Confidence; FR-327, FR-335; S3-T05).

```
agreement  = share of total weight held by non-missing factors whose score has the sign of composite
confidence = 100 * agreement
           - 15 if atr_pct_rank > 90          (volatility.extreme_atr_rank)
           - 10 if any factor quality is degraded
           - 10 if st_dir_w != st_dir_d
           - 10 if rc_stack == -st_dir_d       (ripster.confidence_stack_conflict_penalty)
           - 10 if event_risk
confidence = clip(confidence, 0, 100)
```

Interpretations (PRD A-32): sign(0) is 0, so a composite within 1e-9 of 0 agrees with factors
scoring exactly 0; a null snapshot input (warm-up) never triggers its deduction; the Ripster
deduction needs both `rc_stack` and `st_dir_d` non-zero. The snapshot paths are
`factor.CONFIDENCE_INPUT_PATHS`. The Ripster deduction is implemented here on its own
(S3-T14 adds a `confidence_stack_penalty` helper next to the factor; unify them at integration).
The result lists every deduction that fired, in a fixed order, with a human reason (FR-327).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from supertrends.scoring.config import ScoringConfig
from supertrends.scoring.factor import FactorResult, Quality, format_number, get_path
from supertrends.scoring.ripster_rules import confidence_stack_penalty

__all__ = [
    "ATR_RANK_PENALTY",
    "DEGRADED_PENALTY",
    "EVENT_RISK_PENALTY",
    "WEEKLY_DISAGREE_PENALTY",
    "Confidence",
    "ConfidenceDeduction",
    "compute_confidence",
]

# Deduction sizes fixed by the spec; they have no key in config/scoring.yaml (PRD A-32). The Ripster
# deduction is the config value ripster.confidence_stack_conflict_penalty.
ATR_RANK_PENALTY = 15.0
DEGRADED_PENALTY = 10.0
WEEKLY_DISAGREE_PENALTY = 10.0
EVENT_RISK_PENALTY = 10.0
ZERO_COMPOSITE_TOLERANCE = 1e-9


@dataclass(frozen=True)
class ConfidenceDeduction:
    """One deduction that fired: a stable `code`, the points subtracted, and the reason."""

    code: str
    points: float
    reason: str


@dataclass(frozen=True)
class Confidence:
    """Confidence in 0..100 (unrounded), its starting agreement (0..1), and the deductions."""

    value: float
    agreement: float
    deductions: tuple[ConfidenceDeduction, ...]


def _sign(value: float) -> int:
    if abs(value) <= ZERO_COMPOSITE_TOLERANCE:
        return 0
    return 1 if value > 0 else -1


def _agreement(
    results: Mapping[str, FactorResult], weights: Mapping[str, float], composite: float
) -> float:
    sign = _sign(composite)
    total = 0.0
    same = 0.0
    for fid, result in results.items():
        if result.is_missing:
            continue
        w = weights[fid]
        total += w
        if (result.score > 0) - (result.score < 0) == sign:
            same += w
    return same / total if total > 0 else 0.0


def _direction(value: Any) -> int | None:
    return None if value is None else int(value)


def compute_confidence(  # noqa: PLR0913
    snapshot: Mapping[str, Any],
    results: Mapping[str, FactorResult],
    weights: Mapping[str, float],
    composite: float,
    config: ScoringConfig,
    *,
    event_risk: bool = False,
) -> Confidence:
    """Confidence for one ticker.

    `weights` are effective weights by factor ID (missing factors are ignored whatever weight they
    carry); `composite` is the composite they produced. Raises KeyError naming a snapshot path that
    is absent from `snapshot`.
    """
    atr_rank = get_path(snapshot, "daily.atr_pct_rank")
    st_d = _direction(get_path(snapshot, "daily.supertrend.direction"))
    st_w = _direction(get_path(snapshot, "weekly.supertrend_direction"))
    rc_stack = _direction(get_path(snapshot, "ripster.stack"))

    agreement = _agreement(results, weights, composite)
    deductions: list[ConfidenceDeduction] = []

    cap = config.volatility.extreme_atr_rank
    if atr_rank is not None and atr_rank > cap:
        deductions.append(
            ConfidenceDeduction(
                "atr_pct_rank",
                ATR_RANK_PENALTY,
                f"ATR percentile rank {format_number(float(atr_rank))} is above "
                f"{format_number(float(cap))}",
            )
        )
    degraded = [fid for fid, r in results.items() if r.quality is Quality.DEGRADED]
    if degraded:
        deductions.append(
            ConfidenceDeduction(
                "degraded", DEGRADED_PENALTY, f"Factor data is degraded: {', '.join(degraded)}"
            )
        )
    if st_d is not None and st_w is not None and st_w != st_d:
        deductions.append(
            ConfidenceDeduction(
                "weekly_disagrees",
                WEEKLY_DISAGREE_PENALTY,
                f"Weekly Supertrend direction {format_number(st_w)} differs from daily "
                f"{format_number(st_d)}",
            )
        )
    stack_penalty = confidence_stack_penalty(snapshot, config)
    if stack_penalty and rc_stack and st_d:  # non-zero only when both are set
        deductions.append(
            ConfidenceDeduction(
                "ripster_stack_conflict",
                stack_penalty,
                f"Ripster 5/12 vs 34/50 stack {format_number(rc_stack)} opposes the daily "
                f"Supertrend direction {format_number(st_d)}",
            )
        )
    if event_risk:
        deductions.append(
            ConfidenceDeduction("event_risk", EVENT_RISK_PENALTY, "Earnings event risk")
        )

    value = 100.0 * agreement - math.fsum(d.points for d in deductions)
    return Confidence(
        value=min(100.0, max(0.0, value)), agreement=agreement, deductions=tuple(deductions)
    )
