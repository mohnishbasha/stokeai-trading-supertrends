# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 4, RSI, MACD and OBV divergence (Signal Engine Specification; owner task S3-T02).

Stub: `compute` raises NotImplementedError("S3-T02") until S3-T02 implements the rules. Edit only
this module and its tests; the framework in `supertrends.scoring.factor` is shared.

Snapshot inputs (dotted paths into `compute_snapshot`; `<period>` expands over `sma.periods`):

* `divergences.daily`
* `divergences.weekly`
"""

from collections.abc import Mapping
from typing import Any

from supertrends.scoring.factor import FactorContext, FactorResult

FACTOR_ID = "divergence"
OWNER_TASK = "S3-T02"
INPUT_PATHS: tuple[str, ...] = (
    "divergences.daily",
    "divergences.weekly",
)


class _Divergence:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        raise NotImplementedError(OWNER_TASK)


FACTOR = _Divergence()
