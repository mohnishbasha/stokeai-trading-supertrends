# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 2, SMA stack and slope (Signal Engine Specification, Factor 2; PRD FR-3xx; S3-T02).

Averages are the `sma.periods` (20, 50, 200) of the daily close; below they are `fast`, `mid` and
`slow`. A tie is neither above nor below and adds nothing:

    +-30  close above / below slow (SMA200)
    +-25  mid (SMA50) above / below slow
    +-20  close above / below mid
    +-15  fast (SMA20) slope over `slope_bars` (5) positive / negative
    +-10  golden / death cross (mid vs slow) within the last `cross_lookback` (10) bars
    score = clip(sum, -100, 100)

The snapshot already limits `daily.sma_cross` to the window; the factor checks it again with
`bars - index <= cross_lookback`, so the as-of bar is bar 1 of the window (PRD A-26). A null close,
SMA50 or SMA200 gives `missing`; a null slope scores 0 and marks the factor `degraded` (A-27).

Snapshot inputs (dotted paths into `compute_snapshot`; `<period>` expands over `sma.periods`):

* `bars`
* `daily.close`
* `daily.sma_<period>`
* `daily.sma_slope_<period>`
* `daily.sma_cross`
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

FACTOR_ID = "sma"
OWNER_TASK = "S3-T02"
INPUT_PATHS: tuple[str, ...] = (
    "bars",
    "daily.close",
    "daily.sma_<period>",
    "daily.sma_slope_<period>",
    "daily.sma_cross",
)

CLOSE_VS_SLOW_POINTS = 30.0
MID_VS_SLOW_POINTS = 25.0
CLOSE_VS_MID_POINTS = 20.0
SLOPE_POINTS = 15.0
CROSS_POINTS = 10.0

CLOSE_VS = ReasonTemplate(
    "sma.close_vs", "Close {close} is {relation} the {period}-day average {sma}"
)
MID_VS_SLOW = ReasonTemplate(
    "sma.mid_vs_slow",
    "The {mid_period}-day average {mid} is {relation} the {slow_period}-day average {slow}",
)
SLOPE = ReasonTemplate(
    "sma.slope", "The {period}-day average {sma} {movement} {slope} over {bars} bars"
)
SLOPE_FLAT = ReasonTemplate(
    "sma.slope_flat", "The {period}-day average {sma} was flat over {bars} bars"
)
SLOPE_NA = ReasonTemplate("sma.slope_na", "The {period}-day average slope is not available")
CROSS = ReasonTemplate(
    "sma.cross", "{name} cross ({mid_period}-day {relation} {slow_period}-day) {ago} bars ago"
)
NO_CROSS = ReasonTemplate(
    "sma.no_cross", "No {mid_period}/{slow_period}-day cross in the last {lookback} bars"
)
MISSING = "The moving averages are not available (not enough history)"


def _sign(a: float, b: float) -> int:
    return (a > b) - (a < b)


def _relation(sign: int, *, up: str = "above", down: str = "below") -> str:
    return up if sign > 0 else down if sign < 0 else "equal to"


def _optional(snapshot: Mapping[str, Any], path: str) -> float | None:
    value = get_path(snapshot, path)
    return None if value is None else float(value)


class _Sma:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        cfg = context.config.sma
        fast_p, mid_p, slow_p = cfg.periods[:3]
        try:
            close = _optional(snapshot, "daily.close")
            mid = _optional(snapshot, f"daily.sma_{mid_p}")
            slow = _optional(snapshot, f"daily.sma_{slow_p}")
            fast = _optional(snapshot, f"daily.sma_{fast_p}")
            slope = _optional(snapshot, f"daily.sma_slope_{fast_p}")
            cross = get_path(snapshot, "daily.sma_cross")
            bars = int(get_path(snapshot, "bars"))
        except KeyError:
            return FactorResult.missing(FACTOR_ID, reason=MISSING)
        if close is None or mid is None or slow is None:
            return FactorResult.missing(FACTOR_ID, reason=MISSING)

        close_slow = _sign(close, slow)
        mid_slow = _sign(mid, slow)
        close_mid = _sign(close, mid)
        score = (
            CLOSE_VS_SLOW_POINTS * close_slow
            + MID_VS_SLOW_POINTS * mid_slow
            + CLOSE_VS_MID_POINTS * close_mid
        )
        evidence: list[EvidenceItem] = [
            CLOSE_VS.evidence(
                f"close_vs_sma_{slow_p}",
                slow,
                "price",
                close=close,
                relation=_relation(close_slow),
                period=slow_p,
                sma=slow,
            ),
            MID_VS_SLOW.evidence(
                f"sma_{mid_p}_vs_sma_{slow_p}",
                mid,
                "price",
                mid_period=mid_p,
                mid=mid,
                relation=_relation(mid_slow),
                slow_period=slow_p,
                slow=slow,
            ),
            CLOSE_VS.evidence(
                f"close_vs_sma_{mid_p}",
                mid,
                "price",
                close=close,
                relation=_relation(close_mid),
                period=mid_p,
                sma=mid,
            ),
        ]

        degraded = slope is None or fast is None
        if slope is None or fast is None:
            evidence.append(SLOPE_NA.evidence(f"sma_{fast_p}_slope", None, "price", period=fast_p))
        else:
            slope_sign = _sign(slope, 0.0)
            score += SLOPE_POINTS * slope_sign
            name = f"sma_{fast_p}_slope"
            if slope_sign == 0:
                evidence.append(
                    SLOPE_FLAT.evidence(
                        name, slope, "price", period=fast_p, sma=fast, bars=cfg.slope_bars
                    )
                )
            else:
                evidence.append(
                    SLOPE.evidence(
                        name,
                        slope,
                        "price",
                        period=fast_p,
                        sma=fast,
                        movement="rose" if slope_sign > 0 else "fell",
                        slope=abs(slope),
                        bars=cfg.slope_bars,
                    )
                )

        # `bars - index` counts the as-of bar as 1 (A-26).
        if cross is not None and bars - int(cross["index"]) <= cfg.cross_lookback:
            direction = 1 if int(cross["direction"]) > 0 else -1
            score += CROSS_POINTS * direction
            evidence.append(
                CROSS.evidence(
                    "sma_cross",
                    direction,
                    "cross",
                    name="Golden" if direction > 0 else "Death",
                    mid_period=mid_p,
                    relation="over" if direction > 0 else "under",
                    slow_period=slow_p,
                    ago=bars - int(cross["index"]),
                )
            )
        else:
            evidence.append(
                NO_CROSS.evidence(
                    "sma_cross",
                    0,
                    "cross",
                    mid_period=mid_p,
                    slow_period=slow_p,
                    lookback=cfg.cross_lookback,
                )
            )

        return FactorResult(
            factor_id=FACTOR_ID,
            score=min(SCORE_MAX, max(SCORE_MIN, score)),
            quality=Quality.DEGRADED if degraded else Quality.OK,
            evidence=tuple(evidence),
        )


FACTOR = _Sma()
