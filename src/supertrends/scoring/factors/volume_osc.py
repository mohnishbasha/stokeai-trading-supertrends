# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 9, Volume oscillator (Signal Engine Specification; PRD FR-312; owner task S3-T04).

```
vo        = 100 * (EMA5(volume) - EMA10(volume)) / EMA10(volume)     (indicator, in the snapshot)
ret5      = close[t] / close[t-5] - 1
vo_part   = clip(vo * 2, -60, 60) * sign(ret5)
obv_part  = 40 * sign(least-squares slope of OBV over 20 bars)
score     = clip(vo_part + obv_part, -100, 100)
```

Positive `vo` with a falling price is bearish (selling on rising volume); negative `vo` fades the
move. The oscillator periods and the OBV window come from the scoring config through the
snapshot; the constants here (2, 60, 40) are the rule's own. An input still in warm-up (null)
makes the factor `missing`.

Snapshot inputs (dotted paths into `compute_snapshot`):

* `daily.volume_oscillator`
* `daily.ret_5`
* `daily.obv_slope_sign`
"""

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

FACTOR_ID = "volume_osc"
OWNER_TASK = "S3-T04"
INPUT_PATHS: tuple[str, ...] = (
    "daily.volume_oscillator",
    "daily.ret_5",
    "daily.obv_slope_sign",
)

VO_GAIN = 2.0
VO_PART_LIMIT = 60.0
OBV_PART = 40.0

_VO = ReasonTemplate("volume_osc.vo", "Volume oscillator (5 vs 10 bars) is {vo} percent")
_RET5 = ReasonTemplate("volume_osc.ret5", "The 5-bar return is {ret5}")
_VO_CONFIRM = ReasonTemplate(
    "volume_osc.vo_confirm",
    "Volume confirms the {move} 5-bar move: volume part {part} (oscillator {vo})",
)
_VO_FADE = ReasonTemplate(
    "volume_osc.vo_fade",
    "Volume fades the {move} 5-bar move: volume part {part} (oscillator {vo})",
)
_VO_FLAT = ReasonTemplate(
    "volume_osc.vo_flat", "No directional volume signal, so the volume part is {part}"
)
_OBV = ReasonTemplate("volume_osc.obv", "OBV slope over 20 bars has sign {sign}")
_OBV_PART = ReasonTemplate("volume_osc.obv_part", "OBV part of the volume score is {part}")


def _clip(x: float, low: float, high: float) -> float:
    return max(low, min(high, x))


def _sign(x: float) -> float:
    return float((x > 0) - (x < 0))


class _VolumeOsc:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        vo = get_path(snapshot, "daily.volume_oscillator")
        ret5 = get_path(snapshot, "daily.ret_5")
        obv = get_path(snapshot, "daily.obv_slope_sign")
        if vo is None or ret5 is None or obv is None:
            return FactorResult.missing(
                FACTOR_ID, reason="Volume oscillator inputs are not available yet (warm-up)"
            )
        vo, ret5 = float(vo), float(ret5)
        ret_sign = _sign(ret5)
        obv_sign = int(_sign(float(obv)))
        # `+ 0.0` turns a negative zero into zero
        vo_part = _clip(vo * VO_GAIN, -VO_PART_LIMIT, VO_PART_LIMIT) * ret_sign + 0.0
        obv_part = OBV_PART * obv_sign + 0.0
        score = _clip(vo_part + obv_part, SCORE_MIN, SCORE_MAX)

        if ret_sign == 0.0 or vo == 0.0:
            vo_reason = _VO_FLAT.render(part=vo_part)
        else:
            move = "up" if ret_sign > 0 else "down"
            # volume confirms the move when its part has the move's sign
            template = _VO_CONFIRM if vo > 0 else _VO_FADE
            vo_reason = template.render(move=move, part=vo_part, vo=vo)
        evidence = (
            _VO.evidence("volume_oscillator", vo, "percent", vo=vo),
            _RET5.evidence("ret_5", ret5, "ratio", ret5=ret5),
            EvidenceItem(name="vo_part", value=vo_part, unit="points", reason=vo_reason),
            _OBV.evidence("obv_slope_sign", obv_sign, "sign", sign=obv_sign),
            _OBV_PART.evidence("obv_part", obv_part, "points", part=obv_part),
        )
        return FactorResult(factor_id=FACTOR_ID, score=score, quality=Quality.OK, evidence=evidence)


FACTOR = _VolumeOsc()
