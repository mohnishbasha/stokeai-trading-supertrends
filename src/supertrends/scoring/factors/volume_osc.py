# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 9, Volume oscillator (Signal Engine Specification; owner task S3-T04).

Stub: `compute` raises NotImplementedError("S3-T04") until S3-T04 implements the rules. Edit only
this module and its tests; the framework in `supertrends.scoring.factor` is shared.

Snapshot inputs (dotted paths into `compute_snapshot`; `<period>` expands over `sma.periods`):

* `daily.volume_oscillator`
* `daily.ret_5`
* `daily.obv_slope_sign`
"""

from collections.abc import Mapping
from typing import Any

from supertrends.scoring.factor import FactorContext, FactorResult

FACTOR_ID = "volume_osc"
OWNER_TASK = "S3-T04"
INPUT_PATHS: tuple[str, ...] = (
    "daily.volume_oscillator",
    "daily.ret_5",
    "daily.obv_slope_sign",
)


class _VolumeOsc:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        raise NotImplementedError(OWNER_TASK)


FACTOR = _VolumeOsc()
