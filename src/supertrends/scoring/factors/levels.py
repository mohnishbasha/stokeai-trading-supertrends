# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 7, Support, resistance and 52-week range (Signal Engine Specification; owner task S3-T03).

Rules (BUILD_PROMPT Factor 7; PRD FR-310; scoring.yaml `levels`):

    rr    = d_r / max(d_s, 0.25);  base = clip((rr - 1) * 40, -60, 60)
    +40 breakout (close above a resistance intact yesterday, relative volume >= threshold)
    -40 breakdown (the mirror below support)
    score = clip(base + breakout, -100, 100)

The indicator already includes the 52-week extremes as levels; when one side is still empty
(close at or beyond the 52-week extreme) the distance falls back to that extreme, floored at 0
(ADR-061, PRD A-29).

Snapshot inputs (dotted paths into `compute_snapshot`; `<period>` expands over `sma.periods`):

* `levels.support_resistance`
* `levels.high_52w`
* `levels.low_52w`
* `daily.close`
* `daily.atr`
* `daily.relative_volume`
"""

from collections.abc import Mapping
from typing import Any

from supertrends.scoring.factor import (
    FactorContext,
    FactorResult,
    Quality,
    ReasonTemplate,
    get_path,
)
from supertrends.scoring.factors._values import num

FACTOR_ID = "levels"
OWNER_TASK = "S3-T03"
INPUT_PATHS: tuple[str, ...] = (
    "levels.support_resistance",
    "levels.high_52w",
    "levels.low_52w",
    "daily.close",
    "daily.atr",
    "daily.relative_volume",
)

D_S_FLOOR = 0.25
BASE_SLOPE = 40.0
BASE_CAP = 60.0
BREAKOUT_POINTS = 40.0

_NO_DATA = ReasonTemplate("lv_no_data", "Support and resistance are not available")
_D_S = ReasonTemplate("lv_d_s", "Nearest support is {d_s} ATR below the close")
_D_R = ReasonTemplate("lv_d_r", "Nearest resistance is {d_r} ATR above the close")
_RR = ReasonTemplate("lv_rr", "Room above versus below is {rr} to 1")
_SUPPORT = ReasonTemplate("lv_support", "Nearest support level is {price}")
_RESISTANCE = ReasonTemplate("lv_resistance", "Nearest resistance level is {price}")
_RANGE = ReasonTemplate("lv_range", "The 52-week range is {low} to {high}")
_BREAKOUT = ReasonTemplate(
    "lv_breakout", "Close broke above resistance at {level} on relative volume {rv}"
)
_BREAKDOWN = ReasonTemplate(
    "lv_breakdown", "Close broke below support at {level} on relative volume {rv}"
)
_BASE = ReasonTemplate("lv_base", "Room above versus below contributes {part} points")


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class _Levels:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        sr = get_path(snapshot, "levels.support_resistance")
        close = num(snapshot, "daily.close")
        atr = num(snapshot, "daily.atr")
        high52 = num(snapshot, "levels.high_52w")
        low52 = num(snapshot, "levels.low_52w")
        if (
            sr is None
            or close is None
            or atr is None
            or atr <= 0
            or high52 is None
            or low52 is None
        ):
            return FactorResult.missing(FACTOR_ID, reason=_NO_DATA.render())
        d_s = sr["d_s"]
        d_r = sr["d_r"]
        if d_s is None:
            d_s = max(close - low52, 0.0) / atr
        if d_r is None:
            d_r = max(high52 - close, 0.0) / atr
        d_s, d_r = float(d_s), float(d_r)
        rr = d_r / max(d_s, D_S_FLOOR)
        base = _clip((rr - 1.0) * BASE_SLOPE, -BASE_CAP, BASE_CAP)
        rv = num(snapshot, "daily.relative_volume")
        heavy = rv is not None and rv >= context.config.levels.breakout_rel_volume
        broken = sr.get("broken_level")
        breakout = 0.0
        evidence = [
            _D_S.evidence("d_s", d_s, "atr", d_s=d_s),
            _D_R.evidence("d_r", d_r, "atr", d_r=d_r),
            _RR.evidence("rr", rr, "ratio", rr=rr),
        ]
        for key, template, name in (
            ("nearest_support", _SUPPORT, "nearest_support"),
            ("nearest_resistance", _RESISTANCE, "nearest_resistance"),
        ):
            level = sr.get(key)
            if level is not None:
                price = float(level["price"])
                evidence.append(template.evidence(name, price, "price", price=price))
        evidence.append(_RANGE.evidence("range_52w", high52, "price", low=low52, high=high52))
        if heavy and rv is not None and broken is not None:
            level = float(broken)
            if sr["breakout"]:
                breakout += BREAKOUT_POINTS
                evidence.append(_BREAKOUT.evidence("breakout", level, "price", level=level, rv=rv))
            if sr["breakdown"]:
                breakout -= BREAKOUT_POINTS
                evidence.append(
                    _BREAKDOWN.evidence("breakdown", level, "price", level=level, rv=rv)
                )
        evidence.append(_BASE.evidence("base", base, "points", part=base))
        return FactorResult(
            factor_id=FACTOR_ID,
            score=_clip(base + breakout, -100.0, 100.0) + 0.0,
            quality=Quality.OK,
            evidence=tuple(evidence),
        )


FACTOR = _Levels()
