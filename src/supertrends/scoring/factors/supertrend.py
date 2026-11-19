# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 1, Supertrend (Signal Engine Specification, Factor 1; PRD FR-3xx; S3-T02).

The Supertrend itself is computed by `indicators.supertrend` and carried in the snapshot; this
factor scores it. Directions are +1 up and -1 down (never TradingView's sign). With `d` the daily
direction and `w` the weekly one:

    base      = +60 * d
    weekly    = +25 * d if w == d else -15 * d     (agreement strengthens, conflict weakens)
    freshness = +15 * d if bars_since_flip <= fresh_flip_bars (5) else 0
    stretch   = -10 * d if |st_distance_atr| > stretch_atr (4) else 0
    score     = clip(base + weekly + freshness + stretch, -100, 100)

No daily direction, line or flip age (warm-up) gives a `missing` result. No weekly direction, ATR
or distance scores that part as 0 and marks the factor `degraded` (PRD A-27).

Snapshot inputs (dotted paths into `compute_snapshot`; `<period>` expands over `sma.periods`):

* `daily.supertrend.direction`
* `daily.supertrend.line`
* `daily.bars_since_flip`
* `daily.distance_atr`
* `daily.atr`
* `weekly.supertrend_direction`
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

FACTOR_ID = "supertrend"
OWNER_TASK = "S3-T02"
INPUT_PATHS: tuple[str, ...] = (
    "daily.supertrend.direction",
    "daily.supertrend.line",
    "daily.bars_since_flip",
    "daily.distance_atr",
    "daily.atr",
    "weekly.supertrend_direction",
)

BASE_POINTS = 60.0
WEEKLY_AGREE_POINTS = 25.0
WEEKLY_CONFLICT_POINTS = 15.0
FRESH_POINTS = 15.0
STRETCH_POINTS = 10.0

DIR_D = ReasonTemplate("st.dir_d", "Daily Supertrend is {direction}")
DIR_W = ReasonTemplate(
    "st.dir_w", "Weekly Supertrend is {direction}, which {relation} the daily trend"
)
DIR_W_NA = ReasonTemplate("st.dir_w_na", "Weekly Supertrend is not available")
LINE = ReasonTemplate("st.line", "Supertrend line (invalidation level) is {line}")
ATR = ReasonTemplate("st.atr", "Supertrend ATR({length}) is {atr}")
ATR_NA = ReasonTemplate("st.atr_na", "Supertrend ATR is not available")
FLIP = ReasonTemplate("st.flip", "Supertrend flipped {bars} bars ago")
FLIP_FRESH = ReasonTemplate("st.flip_fresh", "Supertrend flipped {bars} bars ago, a fresh flip")
DIST = ReasonTemplate("st.dist", "Close is {distance} ATR from the Supertrend line")
DIST_STRETCHED = ReasonTemplate(
    "st.dist_stretched",
    "Close is {distance} ATR from the Supertrend line, stretched beyond {limit} ATR (late entry)",
)
DIST_NA = ReasonTemplate("st.dist_na", "Distance from the Supertrend line is not available")
MISSING = "Supertrend is not available (not enough history)"


def _direction_name(direction: int) -> str:
    return "up" if direction > 0 else "down"


def _sign(value: Any) -> int | None:
    """+1 or -1 from a snapshot direction, None when it is null."""
    if value is None:
        return None
    return 1 if float(value) > 0 else -1


def _number(snapshot: Mapping[str, Any], path: str) -> float | None:
    value = get_path(snapshot, path)
    return None if value is None else float(value)


class _Supertrend:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        cfg = context.config.supertrend
        try:
            d = _sign(get_path(snapshot, "daily.supertrend.direction"))
            line = _number(snapshot, "daily.supertrend.line")
            since = _number(snapshot, "daily.bars_since_flip")
            w = _sign(get_path(snapshot, "weekly.supertrend_direction"))
            distance = _number(snapshot, "daily.distance_atr")
            atr = _number(snapshot, "daily.atr")
        except KeyError:
            return FactorResult.missing(FACTOR_ID, reason=MISSING)
        if d is None or line is None or since is None:
            return FactorResult.missing(FACTOR_ID, reason=MISSING)

        degraded = w is None or distance is None or atr is None
        evidence: list[EvidenceItem] = [
            DIR_D.evidence("st_dir_d", d, "direction", direction=_direction_name(d))
        ]
        score = BASE_POINTS * d
        if w is None:
            evidence.append(DIR_W_NA.evidence("st_dir_w", None, "direction"))
        else:
            agrees = w == d
            score += (WEEKLY_AGREE_POINTS if agrees else -WEEKLY_CONFLICT_POINTS) * d
            evidence.append(
                DIR_W.evidence(
                    "st_dir_w",
                    w,
                    "direction",
                    direction=_direction_name(w),
                    relation="agrees with" if agrees else "conflicts with",
                )
            )
        evidence.append(LINE.evidence("st_line", line, "price", line=line))
        if atr is None:
            evidence.append(ATR_NA.evidence("st_atr", None, "price"))
        else:
            evidence.append(ATR.evidence("st_atr", atr, "price", length=cfg.atr_length, atr=atr))

        bars = int(since)
        fresh = since <= cfg.fresh_flip_bars
        if fresh:
            score += FRESH_POINTS * d
        flip = FLIP_FRESH if fresh else FLIP
        evidence.append(flip.evidence("bars_since_flip", bars, "bars", bars=bars))

        if distance is None:
            evidence.append(DIST_NA.evidence("st_distance_atr", None, "atr"))
        elif abs(distance) > cfg.stretch_atr:
            score -= STRETCH_POINTS * d
            evidence.append(
                DIST_STRETCHED.evidence(
                    "st_distance_atr",
                    distance,
                    "atr",
                    distance=distance,
                    limit=cfg.stretch_atr,
                )
            )
        else:
            evidence.append(DIST.evidence("st_distance_atr", distance, "atr", distance=distance))

        return FactorResult(
            factor_id=FACTOR_ID,
            score=min(SCORE_MAX, max(SCORE_MIN, score)),
            quality=Quality.DEGRADED if degraded else Quality.OK,
            evidence=tuple(evidence),
        )


FACTOR = _Supertrend()
