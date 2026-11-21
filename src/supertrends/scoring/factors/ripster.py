# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 12, Ripster EMA Clouds (Signal Engine Specification; owner task S3-T14).

Stub: `compute` raises NotImplementedError("S3-T14") until S3-T14 implements the rules. Edit only
this module and its tests; the framework in `supertrends.scoring.factor` is shared.

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

from supertrends.scoring.factor import FactorContext, FactorResult

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


class _Ripster:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        raise NotImplementedError(OWNER_TASK)


FACTOR = _Ripster()
