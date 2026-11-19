# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 6, Fibonacci retracements and extensions (Signal Engine Specification; owner task S3-T03).

Stub: `compute` raises NotImplementedError("S3-T03") until S3-T03 implements the rules. Edit only
this module and its tests; the framework in `supertrends.scoring.factor` is shared.

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

from supertrends.scoring.factor import FactorContext, FactorResult

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


class _Fibonacci:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        raise NotImplementedError(OWNER_TASK)


FACTOR = _Fibonacci()
