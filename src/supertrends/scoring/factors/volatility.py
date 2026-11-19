# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 8, Volatility squeeze and expansion (Signal Engine Specification; owner task S3-T03).

Stub: `compute` raises NotImplementedError("S3-T03") until S3-T03 implements the rules. Edit only
this module and its tests; the framework in `supertrends.scoring.factor` is shared.

Snapshot inputs (dotted paths into `compute_snapshot`; `<period>` expands over `sma.periods`):

* `daily.squeeze`
* `daily.expansion`
* `daily.atr_pct_rank`
* `daily.bbw_rank`
* `daily.supertrend.direction`
* `daily.close`
* `daily.close_lag_3`
* `daily.atr`
* `daily.atr_pct`
* `daily.hv20`
* `daily.bandwidth`
"""

from collections.abc import Mapping
from typing import Any

from supertrends.scoring.factor import FactorContext, FactorResult

FACTOR_ID = "volatility"
OWNER_TASK = "S3-T03"
INPUT_PATHS: tuple[str, ...] = (
    "daily.squeeze",
    "daily.expansion",
    "daily.atr_pct_rank",
    "daily.bbw_rank",
    "daily.supertrend.direction",
    "daily.close",
    "daily.close_lag_3",
    "daily.atr",
    "daily.atr_pct",
    "daily.hv20",
    "daily.bandwidth",
)


class _Volatility:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        raise NotImplementedError(OWNER_TASK)


FACTOR = _Volatility()
