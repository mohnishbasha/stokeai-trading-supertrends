# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 10, Order flow estimate (Signal Engine Specification; owner task S3-T04).

Stub: `compute` raises NotImplementedError("S3-T04") until S3-T04 implements the rules. Edit only
this module and its tests; the framework in `supertrends.scoring.factor` is shared.

Snapshot inputs (dotted paths into `compute_snapshot`; `<period>` expands over `sma.periods`):

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

from supertrends.scoring.factor import FactorContext, FactorResult

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


class _Flow:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        raise NotImplementedError(OWNER_TASK)


FACTOR = _Flow()
