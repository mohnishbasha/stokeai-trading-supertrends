# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 4, RSI, MACD and OBV divergence (Signal Engine Specification, Factor 4; FR-3xx; S3-T02).

The detector (`indicators.divergence`) finds divergences between the two most recent confirmed
pivots, so a divergence is known `pivot_width` bars late and never uses an unconfirmed pivot
(NFR-007). This factor scores the records the snapshot carries:

    RSI +-40, MACD histogram +-35, OBV +-25   (bullish +, bearish -; points from the config)
    hidden divergences count at `hidden_multiplier` (0.5) of that value
    x `weekly_confirm_multiplier` (1.25), once, when the same divergence (oscillator, kind and
    side) also exists on weekly bars
    score = clip(sum, -100, 100)

Only divergences whose second pivot is within `recency_bars` (15) of the as-of bar count:
`(bars - 1) - p2 <= recency_bars`, checked again here on the daily and the weekly records (PRD
A-26). The weekly confirmation needs at least one counted daily divergence of the same type; a
weekly divergence alone scores 0 (PRD A-27). An unknown oscillator raises ValueError.

Snapshot inputs (dotted paths into `compute_snapshot`; `<period>` expands over `sma.periods`):

* `bars`
* `weekly.weeks`
* `divergences.daily`
* `divergences.weekly`
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from supertrends.scoring.factor import (
    SCORE_MAX,
    SCORE_MIN,
    EvidenceItem,
    FactorContext,
    FactorResult,
    Quality,
    ReasonTemplate,
    get_path,
)

FACTOR_ID = "divergence"
OWNER_TASK = "S3-T02"
INPUT_PATHS: tuple[str, ...] = (
    "bars",
    "weekly.weeks",
    "divergences.daily",
    "divergences.weekly",
)

OSCILLATOR_NAMES = {"rsi": "RSI", "macd_hist": "MACD histogram", "obv": "OBV"}

DIVERGENCE = ReasonTemplate(
    "div.divergence",
    "{kind} {side} {oscillator} divergence: price {pivot} {price1} then {price2} "
    "while {oscillator} went {osc1} then {osc2}, {ago} bars ago",
)
WEEKLY_CONFIRM = ReasonTemplate(
    "div.weekly_confirm", "The same divergence on weekly bars multiplies the total by {multiplier}"
)
NONE_FOUND = ReasonTemplate(
    "div.none",
    "No RSI, MACD histogram, or OBV divergence with a second pivot in the last {bars} bars",
)
MISSING = "Divergences are not available"


def _recent(records: Any, bars: int, recency: int) -> list[Mapping[str, Any]]:
    """The records whose second pivot is within `recency` bars of the as-of bar."""
    return [r for r in records if (bars - 1) - int(r["p2"]) <= recency]


def _type(record: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(record["oscillator"]), str(record["kind"]), str(record["side"]))


class _Divergence:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        cfg = context.config.divergence
        points = cfg.points.model_dump()
        try:
            bars = int(get_path(snapshot, "bars"))
            weeks = int(get_path(snapshot, "weekly.weeks"))
            daily = _recent(get_path(snapshot, "divergences.daily"), bars, cfg.recency_bars)
            weekly = _recent(get_path(snapshot, "divergences.weekly"), weeks, cfg.recency_bars)
        except (KeyError, TypeError):
            return FactorResult.missing(FACTOR_ID, reason=MISSING)

        confirmed = {_type(r) for r in weekly}
        total = 0.0
        confirmed_any = False
        evidence: list[EvidenceItem] = []
        for rec in daily:
            oscillator, kind, side = _type(rec)
            if oscillator not in points:
                msg = f"no divergence points for oscillator {oscillator!r}"
                raise ValueError(msg)
            value = points[oscillator] * (1.0 if side == "bullish" else -1.0)
            if kind == "hidden":
                value *= cfg.hidden_multiplier
            total += value
            confirmed_any = confirmed_any or (oscillator, kind, side) in confirmed
            name = OSCILLATOR_NAMES[oscillator]
            evidence.append(
                DIVERGENCE.evidence(
                    f"{oscillator}_{kind}_{side}",
                    value,
                    "points",
                    kind=kind.capitalize(),
                    side=side,
                    oscillator=name,
                    pivot="low" if side == "bullish" else "high",
                    price1=float(rec["price1"]),
                    price2=float(rec["price2"]),
                    osc1=float(rec["osc1"]),
                    osc2=float(rec["osc2"]),
                    ago=(bars - 1) - int(rec["p2"]),
                )
            )
        if confirmed_any:
            total *= cfg.weekly_confirm_multiplier
            evidence.append(
                WEEKLY_CONFIRM.evidence(
                    "weekly_confirmation",
                    cfg.weekly_confirm_multiplier,
                    "multiplier",
                    multiplier=cfg.weekly_confirm_multiplier,
                )
            )
        if not evidence:
            evidence.append(
                NONE_FOUND.evidence("divergence_count", 0, "count", bars=cfg.recency_bars)
            )

        return FactorResult(
            factor_id=FACTOR_ID,
            score=min(SCORE_MAX, max(SCORE_MIN, total)),
            quality=Quality.OK,
            evidence=tuple(evidence),
        )


FACTOR = _Divergence()
