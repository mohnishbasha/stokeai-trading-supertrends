# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 12, Ripster EMA Clouds (Signal Engine Specification; owner task S3-T14).

Score (FR-333), with the points read from `ripster.points` (30, 20, 20, 10, 10, 10):

    bias     = 30 * pos(c3)       close above, inside (0) or below the 34/50 cloud
    trend    = 20 * cloud_dir(c2)
    stacking = 20 * stack
    mid      = 10 * cloud_dir(c3)
    long     = 10 * pos(c5)
    pullback = 10 * stack when stack != 0 and the snapshot's pullback flag is set, else 0
    score    = clip(sum, -100, 100)

The pullback flag is computed per bar by `indicators.ripster_clouds.ripster_pullback` over the last
`ripster.pullback_lookback_bars` bars including the as-of bar (t-2 to t for 3; PRD A-25) and is
read from the snapshot. The 72/89 cloud is evidence only and never scored. A null core input
(fewer than 50 bars) makes the factor `missing`; a null 180/200 position (50 to 199 bars) scores
`long` 0 and marks the factor `degraded` (PRD A-31, ADR-063). The confidence deduction, the
selection gate and the evidence block live in `supertrends.scoring.ripster_rules`.

Snapshot inputs (dotted paths into `compute_snapshot`; `<period>` expands over `sma.periods`):

* `ripster.bias`
* `ripster.stack`
* `ripster.bars_since_stack_flip`
* `ripster.pullback`
* `ripster.c2_dir`
* `ripster.c3_dir`
* `ripster.c3_top`
* `ripster.c3_bot`
* `ripster.dir_w`
* `ripster.clouds.c1.top`
* `ripster.clouds.c1.bot`
* `ripster.clouds.c1.dir`
* `ripster.clouds.c1.pos`
* `ripster.clouds.c2.top`
* `ripster.clouds.c2.bot`
* `ripster.clouds.c2.dir`
* `ripster.clouds.c2.pos`
* `ripster.clouds.c3.top`
* `ripster.clouds.c3.bot`
* `ripster.clouds.c3.dir`
* `ripster.clouds.c3.pos`
* `ripster.clouds.c4.top`
* `ripster.clouds.c4.bot`
* `ripster.clouds.c4.dir`
* `ripster.clouds.c4.pos`
* `ripster.clouds.c5.top`
* `ripster.clouds.c5.bot`
* `ripster.clouds.c5.dir`
* `ripster.clouds.c5.pos`
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

FACTOR_ID = "ripster"
OWNER_TASK = "S3-T14"
INPUT_PATHS: tuple[str, ...] = (
    "ripster.bias",
    "ripster.stack",
    "ripster.bars_since_stack_flip",
    "ripster.pullback",
    "ripster.c2_dir",
    "ripster.c3_dir",
    "ripster.c3_top",
    "ripster.c3_bot",
    "ripster.dir_w",
    "ripster.clouds.c1.top",
    "ripster.clouds.c1.bot",
    "ripster.clouds.c1.dir",
    "ripster.clouds.c1.pos",
    "ripster.clouds.c2.top",
    "ripster.clouds.c2.bot",
    "ripster.clouds.c2.dir",
    "ripster.clouds.c2.pos",
    "ripster.clouds.c3.top",
    "ripster.clouds.c3.bot",
    "ripster.clouds.c3.dir",
    "ripster.clouds.c3.pos",
    "ripster.clouds.c4.top",
    "ripster.clouds.c4.bot",
    "ripster.clouds.c4.dir",
    "ripster.clouds.c4.pos",
    "ripster.clouds.c5.top",
    "ripster.clouds.c5.bot",
    "ripster.clouds.c5.dir",
    "ripster.clouds.c5.pos",
)

_UNAVAILABLE = "Ripster EMA Clouds are not available: fewer than 50 bars of history"

_ADD = ", adding {points} points"
_SUB = ", subtracting {points} points"

# One template per state of each rule line (a reason per rule that fired, FR-5xx).
_T = {
    ("bias", 1): ReasonTemplate("ripster.bias.above", "Close is above the 34/50 cloud" + _ADD),
    ("bias", -1): ReasonTemplate("ripster.bias.below", "Close is below the 34/50 cloud" + _SUB),
    ("bias", 0): ReasonTemplate(
        "ripster.bias.inside", "Close is inside the 34/50 cloud, adding no points"
    ),
    ("trend", 1): ReasonTemplate("ripster.trend.up", "The 5/12 cloud is bullish" + _ADD),
    ("trend", -1): ReasonTemplate("ripster.trend.down", "The 5/12 cloud is bearish" + _SUB),
    ("stacking", 1): ReasonTemplate(
        "ripster.stacking.up", "The 5/12 cloud is fully above the 34/50 cloud" + _ADD
    ),
    ("stacking", -1): ReasonTemplate(
        "ripster.stacking.down", "The 5/12 cloud is fully below the 34/50 cloud" + _SUB
    ),
    ("stacking", 0): ReasonTemplate(
        "ripster.stacking.overlap",
        "The 5/12 and 34/50 clouds overlap, adding no points",
    ),
    ("mid", 1): ReasonTemplate("ripster.mid.up", "The 34/50 cloud is bullish" + _ADD),
    ("mid", -1): ReasonTemplate("ripster.mid.down", "The 34/50 cloud is bearish" + _SUB),
    ("long", 1): ReasonTemplate("ripster.long.above", "Close is above the 180/200 cloud" + _ADD),
    ("long", -1): ReasonTemplate("ripster.long.below", "Close is below the 180/200 cloud" + _SUB),
    ("long", 0): ReasonTemplate(
        "ripster.long.inside", "Close is inside the 180/200 cloud, adding no points"
    ),
    ("pullback", 1): ReasonTemplate(
        "ripster.pullback.up", "Held pullback into the 8/9 cloud" + _ADD
    ),
    ("pullback", -1): ReasonTemplate(
        "ripster.pullback.down", "Held bounce into the 8/9 cloud" + _SUB
    ),
    ("pullback", 0): ReasonTemplate(
        "ripster.pullback.none", "No held test of the 8/9 cloud, adding no points"
    ),
}
_LONG_UNAVAILABLE = ReasonTemplate(
    "ripster.long.unavailable",
    "The 180/200 cloud needs 200 bars of history, adding no points",
)
_FLIP = ReasonTemplate(
    "ripster.rc_bars_since_stack_flip", "The cloud stack last flipped {bars} bars ago"
)
_FLIP_NONE = ReasonTemplate(
    "ripster.rc_bars_since_stack_flip.none",
    "The 5/12 and 34/50 clouds overlap, so there is no stack flip",
)
_BIAS_NOTE = ReasonTemplate("ripster.rc_bias", "Close position against the 34/50 cloud is {value}")
_STACK_NOTE = ReasonTemplate("ripster.rc_stack", "The cloud stack is {value}")
_TOP = ReasonTemplate("ripster.rc_c3_top", "The 34/50 cloud top is {value}")
_BOT = ReasonTemplate("ripster.rc_c3_bot", "The 34/50 cloud bottom is {value}")
_DIR_W = ReasonTemplate("ripster.rc_dir_w", "The weekly 34/50 cloud direction is {value}")


def _sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def _num(value: float) -> float | int:
    """An int when the value is whole (30.0 becomes 30), so reasons print `30`, not `30.00`."""
    return int(value) if float(value).is_integer() else float(value)


def _opt(snapshot: Mapping[str, Any], path: str) -> float | None:
    value = get_path(snapshot, path)
    return None if value is None else float(value)


class _Ripster:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        pts = context.config.ripster.points
        bias = _opt(snapshot, "ripster.bias")
        stack = _opt(snapshot, "ripster.stack")
        c2_dir = _opt(snapshot, "ripster.c2_dir")
        c3_dir = _opt(snapshot, "ripster.c3_dir")
        if bias is None or stack is None or c2_dir is None or c3_dir is None:
            return FactorResult.missing(FACTOR_ID, reason=_UNAVAILABLE)
        c5_pos = _opt(snapshot, "ripster.clouds.c5.pos")
        pullback = _opt(snapshot, "ripster.pullback")

        held = stack != 0 and pullback is not None and pullback != 0
        # (name, sign of the rule input, points configured, signed contribution)
        lines = (
            ("bias", _sign(bias), pts.bias, pts.bias * _sign(bias)),
            ("trend", _sign(c2_dir), pts.trend, pts.trend * _sign(c2_dir)),
            ("stacking", _sign(stack), pts.stack, pts.stack * _sign(stack)),
            ("mid", _sign(c3_dir), pts.mid, pts.mid * _sign(c3_dir)),
            ("long", _sign(c5_pos or 0.0), pts.long, pts.long * _sign(c5_pos or 0.0)),
            (
                "pullback",
                _sign(stack) if held else 0,
                pts.pullback,
                pts.pullback * _sign(stack) if held else 0.0,
            ),
        )
        evidence: list[EvidenceItem] = []
        for name, sign, configured, contribution in lines:
            if name == "long" and c5_pos is None:
                reason = _LONG_UNAVAILABLE.render()
            else:
                template = _T[(name, sign)]
                reason = (
                    template.render(points=_num(configured))
                    if "points}" in template.template
                    else template.render()
                )
            evidence.append(
                EvidenceItem(name=name, value=_num(contribution), unit="points", reason=reason)
            )

        score = max(SCORE_MIN, min(SCORE_MAX, sum(c for *_, c in lines)))
        evidence.extend(self._derived(snapshot, bias, stack))
        quality = Quality.OK if c5_pos is not None else Quality.DEGRADED
        return FactorResult(
            factor_id=FACTOR_ID, score=float(score), quality=quality, evidence=tuple(evidence)
        )

    @staticmethod
    def _derived(snapshot: Mapping[str, Any], bias: float, stack: float) -> list[EvidenceItem]:
        """The `rc_*` values of the spec as evidence items (FR-333)."""
        flip = _opt(snapshot, "ripster.bars_since_stack_flip")
        top = _opt(snapshot, "ripster.c3_top")
        bot = _opt(snapshot, "ripster.c3_bot")
        dir_w = _opt(snapshot, "ripster.dir_w")
        items = [
            _BIAS_NOTE.evidence("rc_bias", _sign(bias), "direction", value=_sign(bias)),
            _STACK_NOTE.evidence("rc_stack", _sign(stack), "direction", value=_sign(stack)),
        ]
        if flip is None:
            items.append(_FLIP_NONE.evidence("rc_bars_since_stack_flip", None, "bars"))
        else:
            items.append(
                _FLIP.evidence("rc_bars_since_stack_flip", int(flip), "bars", bars=int(flip))
            )
        for name, template, value in (("rc_c3_top", _TOP, top), ("rc_c3_bot", _BOT, bot)):
            if value is None:
                items.append(
                    EvidenceItem(
                        name=name,
                        value=None,
                        unit="price",
                        reason="The 34/50 cloud edge is not available",
                    )
                )
            else:
                items.append(template.evidence(name, value, "price", value=value))
        if dir_w is None:
            items.append(
                EvidenceItem(
                    name="rc_dir_w",
                    value=None,
                    unit="direction",
                    reason="The weekly 34/50 cloud direction is not available",
                )
            )
        else:
            items.append(_DIR_W.evidence("rc_dir_w", _sign(dir_w), "direction", value=_sign(dir_w)))
        return items


FACTOR = _Ripster()
