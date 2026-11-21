# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 5, Mean reversion (Signal Engine Specification; owner task S3-T03).

Rules (BUILD_PROMPT Factor 5; PRD FR-307; scoring.yaml `mean_reversion`):

    z_part   = -60 * clip(z / z_cap, -1, 1)
    rsi_part = +40 if rsi <= rsi_low; -40 if rsi >= rsi_high; else linear from +40 to -40
    score    = clip(z_part + rsi_part, -100, 100)

`pct_b` is evidence only. A null z-score (zero standard deviation) contributes 0 and degrades the
factor; a null RSI likewise; both null is `missing`. The factor fights the trend factors on
purpose; the regime weights decide who wins.

Snapshot inputs (dotted paths into `compute_snapshot`; `<period>` expands over `sma.periods`):

* `daily.zscore`
* `daily.rsi`
* `daily.pct_b`
* `daily.close`
"""

from collections.abc import Mapping
from typing import Any

from supertrends.scoring.factor import (
    FactorContext,
    FactorResult,
    Quality,
    ReasonTemplate,
)
from supertrends.scoring.factors._values import num

FACTOR_ID = "mean_reversion"
OWNER_TASK = "S3-T03"
INPUT_PATHS: tuple[str, ...] = (
    "daily.zscore",
    "daily.rsi",
    "daily.pct_b",
    "daily.close",
)

Z_PART_MAX = 60.0
RSI_PART_MAX = 40.0

_Z = ReasonTemplate("mr_zscore", "Close is {z} standard deviations from its 20-day average")
_Z_NA = ReasonTemplate("mr_zscore_na", "Z-score is not available (zero price variation)")
_RSI = ReasonTemplate("mr_rsi", "RSI({length}) is {rsi}")
_RSI_NA = ReasonTemplate("mr_rsi_na", "RSI is not available")
_PCT_B = ReasonTemplate("mr_pct_b", "Close sits at {pct_b} of the Bollinger band width")
_Z_PART = ReasonTemplate("mr_z_part", "Stretch from the average contributes {part} points")
_RSI_PART = ReasonTemplate("mr_rsi_part", "RSI contributes {part} points")
_NONE = ReasonTemplate("mr_none", "Neither z-score nor RSI is available")


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class _MeanReversion:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        cfg = context.config.mean_reversion
        z = num(snapshot, "daily.zscore")
        rsi = num(snapshot, "daily.rsi")
        pct_b = num(snapshot, "daily.pct_b")
        if z is None and rsi is None:
            return FactorResult.missing(FACTOR_ID, reason=_NONE.render())
        evidence = []
        z_part = 0.0
        if z is None:
            evidence.append(_Z_NA.evidence("zscore", None, "stdev"))
        else:
            z_part = -Z_PART_MAX * _clip(z / cfg.z_cap, -1.0, 1.0)
            evidence.append(_Z.evidence("zscore", z, "stdev", z=z))
        rsi_part = 0.0
        if rsi is None:
            evidence.append(_RSI_NA.evidence("rsi", None, "index"))
        else:
            span = cfg.rsi_high - cfg.rsi_low
            rsi_part = _clip(
                RSI_PART_MAX - 2 * RSI_PART_MAX * (rsi - cfg.rsi_low) / span,
                -RSI_PART_MAX,
                RSI_PART_MAX,
            )
            evidence.append(_RSI.evidence("rsi", rsi, "index", length=cfg.rsi_length, rsi=rsi))
        if pct_b is not None:
            evidence.append(_PCT_B.evidence("pct_b", pct_b, "ratio", pct_b=pct_b))
        evidence.append(_Z_PART.evidence("z_part", z_part, "points", part=z_part))
        evidence.append(_RSI_PART.evidence("rsi_part", rsi_part, "points", part=rsi_part))
        degraded = z is None or rsi is None
        return FactorResult(
            factor_id=FACTOR_ID,
            score=_clip(z_part + rsi_part, -100.0, 100.0) + 0.0,
            quality=Quality.DEGRADED if degraded else Quality.OK,
            evidence=tuple(evidence),
        )


FACTOR = _MeanReversion()
