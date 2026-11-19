# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 11, Fundamentals (Signal Engine Specification; owner task S5-T04).

Sprint 3 stub: always returns a `missing` result with score 0, so the composite leaves it out and
redistributes its weight (spec, Factor 11). S5-T04 replaces it with the real rules when the
fundamentals data arrives.

Snapshot inputs:

* none: fundamentals reach the factor through `FactorContext.fundamentals`
"""

from collections.abc import Mapping
from typing import Any

from supertrends.scoring.factor import FactorContext, FactorResult

FACTOR_ID = "fundamentals"
OWNER_TASK = "S5-T04"
INPUT_PATHS: tuple[str, ...] = ()

MISSING_REASON = "Fundamentals are not available for this ticker"


class _Fundamentals:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        # Sprint 3 has no fundamentals data: always missing, score 0, weight redistributed.
        return FactorResult.missing(FACTOR_ID, reason=MISSING_REASON)


FACTOR = _Fundamentals()
