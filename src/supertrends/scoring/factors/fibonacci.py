# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 6, Fibonacci retracements and extensions (Signal Engine Specification; owner task S3-T03).

Rules (BUILD_PROMPT Factor 6; PRD FR-308, FR-309; scoring.yaml `fibonacci`). Rules are tried in
the order listed, first match wins (ADR-061, PRD A-28). For an up leg (A low, B high):

    +60 near 38.2 and holding; +70 near 50.0 and holding; +80 near 61.8 and holding
    -50 close below the 78.6 level; +20 close above B; 0 otherwise

A down leg mirrors every rule with the signs flipped. No leg: score 0, quality `degraded`.
`near` and `holding` are the S2-T06 indicator tests (`supertrends.indicators.fibonacci`).

Snapshot inputs (dotted paths into `compute_snapshot`; `<period>` expands over `sma.periods`):

* `fib.leg`
* `fib.retracements`
* `fib.extensions`
* `daily.close`
* `daily.prev_close`
* `daily.low`
* `daily.high`
* `daily.atr`
"""

from collections.abc import Mapping
from typing import Any

from supertrends.indicators.fibonacci import holding, near
from supertrends.scoring.factor import (
    FactorContext,
    FactorResult,
    Quality,
    ReasonTemplate,
    get_path,
)
from supertrends.scoring.factors._values import num

FACTOR_ID = "fibonacci"
OWNER_TASK = "S3-T03"
INPUT_PATHS: tuple[str, ...] = (
    "fib.leg",
    "fib.retracements",
    "fib.extensions",
    "daily.close",
    "daily.prev_close",
    "daily.low",
    "daily.high",
    "daily.atr",
)

# (retracement ratio, points for an up leg); the mirror flips the sign. Listed order is the rule
# order, first match wins.
_HOLD_RULES: tuple[tuple[float, float], ...] = ((0.382, 60.0), (0.5, 70.0), (0.618, 80.0))
_FAIL_RATIO = 0.786
_FAIL_POINTS = -50.0
_RESUME_POINTS = 20.0
_NEXT_RATIO = 1.272
_FAR_RATIO = 1.618

_LEG = ReasonTemplate(
    "fib_leg", "Last swing leg runs {direction} from {a} to {b}; levels are measured back from {b}"
)
_NO_LEG = ReasonTemplate("fib_no_leg", "No completed swing leg qualifies, so Fibonacci is neutral")
_NO_DATA = ReasonTemplate("fib_no_data", "Price, prior close or ATR is not available")
_HOLD = ReasonTemplate(
    "fib_hold",
    "Price is within {near_atr} ATR of the {pct} percent retracement at {level} and holding",
)
_FAILED = ReasonTemplate(
    "fib_failed",
    "Close {close} is beyond the {pct} percent retracement at {level}: the swing failed",
)
_RESUMED = ReasonTemplate(
    "fib_resumed", "Close {close} is beyond the swing extreme {b}: the leg resumed"
)
_NONE = ReasonTemplate("fib_none", "Price is not at a Fibonacci level that decides the score")
_NEXT = ReasonTemplate("fib_next", "Next level is the 127.2 percent extension at {level}")
_FAR = ReasonTemplate("fib_far", "Further level is the 161.8 percent extension at {level}")


def _prices_by_ratio(rows: Any) -> dict[float, float]:
    return {round(float(r["ratio"]), 3): float(r["price"]) for r in rows}


def _pct(ratio: float) -> float:
    return round(ratio * 100, 1)


class _Fibonacci:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        near_atr = context.config.fibonacci.near_atr
        close = num(snapshot, "daily.close")
        prev_close = num(snapshot, "daily.prev_close")
        low = num(snapshot, "daily.low")
        high = num(snapshot, "daily.high")
        atr = num(snapshot, "daily.atr")
        if close is None or prev_close is None or low is None or high is None or atr is None:
            return FactorResult.missing(FACTOR_ID, reason=_NO_DATA.render())
        leg = get_path(snapshot, "fib.leg")
        retr = _prices_by_ratio(get_path(snapshot, "fib.retracements"))
        if leg is None or not all(r in retr for r, _ in _HOLD_RULES) or _FAIL_RATIO not in retr:
            item = _NO_LEG.evidence("fib_leg", None, "leg")
            return FactorResult(
                factor_id=FACTOR_ID, score=0.0, quality=Quality.DEGRADED, evidence=(item,)
            )
        d = 1 if int(leg["direction"]) > 0 else -1
        a, b = float(leg["a_price"]), float(leg["b_price"])
        extreme = low if d > 0 else high
        evidence = [
            _LEG.evidence("fib_leg", d, "direction", direction="up" if d > 0 else "down", a=a, b=b)
        ]
        score = 0.0
        for ratio, points in _HOLD_RULES:
            level = retr[ratio]
            if near(close, level, atr, near_atr) and holding(
                d, close, prev_close, extreme, level, atr, near_atr
            ):
                score = d * points
                evidence.append(
                    _HOLD.evidence(
                        "fib_level",
                        level,
                        "price",
                        near_atr=near_atr,
                        pct=_pct(ratio),
                        level=level,
                    )
                )
                break
        else:
            fail_level = retr[_FAIL_RATIO]
            if d * (close - fail_level) < 0:
                score = d * _FAIL_POINTS
                evidence.append(
                    _FAILED.evidence(
                        "fib_failed",
                        fail_level,
                        "price",
                        close=close,
                        pct=_pct(_FAIL_RATIO),
                        level=fail_level,
                    )
                )
            elif d * (close - b) > 0:
                score = d * _RESUME_POINTS
                evidence.append(_RESUMED.evidence("fib_resumed", b, "price", close=close, b=b))
            else:
                evidence.append(_NONE.evidence("fib_rule", False, "flag"))
        ext = _prices_by_ratio(get_path(snapshot, "fib.extensions"))
        if _NEXT_RATIO in ext:
            evidence.append(
                _NEXT.evidence(
                    "fib_next_level_127_2", ext[_NEXT_RATIO], "price", level=ext[_NEXT_RATIO]
                )
            )
        if _FAR_RATIO in ext:
            evidence.append(
                _FAR.evidence("fib_level_161_8", ext[_FAR_RATIO], "price", level=ext[_FAR_RATIO])
            )
        return FactorResult(
            factor_id=FACTOR_ID, score=score + 0.0, quality=Quality.OK, evidence=tuple(evidence)
        )


FACTOR = _Fibonacci()
