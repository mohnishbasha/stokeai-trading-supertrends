# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 10, Buy / sell volume, estimated order flow (Signal Engine Specification; FR-313; S3-T04).

```
score = clip(delta_pct_10 * 300, -50, 50) + clip(cmf20 * 200, -50, 50)
```

`delta_pct_10` and its quality come from the snapshot's `flow` block (`indicators.flow`):
`intraday` (5-minute bars on at least 8 of the last 10 sessions), `daily_estimate` (the same
formula on daily bars; the factor weight is multiplied by `flow.daily_estimate_weight_multiplier`,
returned as `FactorResult.weight_multiplier` for the weights step), or `trades` (the optional
tick-rule upgrade; scored like `intraday`, PRD A-30). Accumulation and distribution days of the
last 20 sessions are reported as evidence and do not move the score. An input still in warm-up
(null) makes the factor `missing`.

Snapshot inputs (dotted paths into `compute_snapshot`):

* `flow.delta_pct_10`
* `flow.quality`
* `flow.daily_fallback`
* `flow.intraday_sessions`
* `daily.cmf`
* `daily.acc_dist.accumulation`
* `daily.acc_dist.distribution`
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

FACTOR_ID = "flow"
OWNER_TASK = "S3-T04"
INPUT_PATHS: tuple[str, ...] = (
    "flow.delta_pct_10",
    "flow.quality",
    "flow.daily_fallback",
    "flow.intraday_sessions",
    "daily.cmf",
    "daily.acc_dist.accumulation",
    "daily.acc_dist.distribution",
)

DELTA_GAIN = 300.0
CMF_GAIN = 200.0
PART_LIMIT = 50.0

_QUALITIES = {
    "intraday": Quality.OK,
    "trades": Quality.OK,
    "daily_estimate": Quality.DAILY_ESTIMATE,
}

_DELTA = ReasonTemplate(
    "flow.delta", "Estimated buy minus sell volume averaged over 10 sessions is {delta} of volume"
)
_CMF = ReasonTemplate("flow.cmf", "Chaikin money flow over 20 bars is {cmf}")
_QUALITY = ReasonTemplate("flow.quality", "Order flow data quality is {quality}")
_SESSIONS = ReasonTemplate("flow.sessions", "{sessions} of the last 10 sessions have 5-minute bars")
_ACC = ReasonTemplate(
    "flow.accumulation", "{days} accumulation days in the last 20 sessions (up close, volume 1.5x)"
)
_DIST = ReasonTemplate(
    "flow.distribution",
    "{days} distribution days in the last 20 sessions (down close, volume 1.5x)",
)
_DISCOUNT = ReasonTemplate(
    "flow.discount", "Daily-bar estimate: the factor weight is multiplied by {multiplier}"
)


def _clip(x: float, low: float, high: float) -> float:
    return max(low, min(high, x))


class _Flow:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        delta = get_path(snapshot, "flow.delta_pct_10")
        cmf = get_path(snapshot, "daily.cmf")
        quality_name = str(get_path(snapshot, "flow.quality"))
        if quality_name not in _QUALITIES:
            msg = f"unknown flow quality {quality_name!r}; expected one of {sorted(_QUALITIES)}"
            raise ValueError(msg)
        if delta is None or cmf is None:
            return FactorResult.missing(
                FACTOR_ID, reason="Order flow inputs are not available yet (warm-up)"
            )
        delta, cmf = float(delta), float(cmf)
        score = _clip(delta * DELTA_GAIN, -PART_LIMIT, PART_LIMIT) + _clip(
            cmf * CMF_GAIN, -PART_LIMIT, PART_LIMIT
        )
        quality = _QUALITIES[quality_name]
        multiplier = 1.0
        if quality is Quality.DAILY_ESTIMATE:
            multiplier = context.config.flow.daily_estimate_weight_multiplier

        sessions = int(get_path(snapshot, "flow.intraday_sessions"))
        evidence = [
            _DELTA.evidence("delta_pct_10", delta, "ratio", delta=delta),
            _CMF.evidence("cmf_20", cmf, "ratio", cmf=cmf),
            _QUALITY.evidence("flow_quality", quality_name, "label", quality=quality_name),
            _SESSIONS.evidence("intraday_sessions", sessions, "sessions", sessions=sessions),
        ]
        if quality is Quality.DAILY_ESTIMATE:
            evidence.append(
                _DISCOUNT.evidence("weight_multiplier", multiplier, "ratio", multiplier=multiplier)
            )
        for name, path, template in (
            ("accumulation_days", "daily.acc_dist.accumulation", _ACC),
            ("distribution_days", "daily.acc_dist.distribution", _DIST),
        ):
            days = get_path(snapshot, path)
            if days is not None:
                evidence.append(template.evidence(name, int(days), "days", days=int(days)))
        return FactorResult(
            factor_id=FACTOR_ID,
            score=score,
            quality=quality,
            evidence=tuple(evidence),
            weight_multiplier=multiplier,
        )


FACTOR = _Flow()
