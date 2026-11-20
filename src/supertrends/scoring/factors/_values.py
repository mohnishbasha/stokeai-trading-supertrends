# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Typed reads of snapshot values for Factors 5 to 8 (S3-T03).

A snapshot value that is null (an indicator in warm-up, or undefined such as the z-score of a flat
series) reads as None. A path that is absent raises KeyError: that is a schema break, not data.
"""

import math
from collections.abc import Mapping
from typing import Any

from supertrends.scoring.factor import get_path

__all__ = ["num", "sign"]


def num(snapshot: Mapping[str, Any], path: str) -> float | None:
    """The finite number at `path`, or None when null or not finite."""
    value = get_path(snapshot, path)
    if value is None or isinstance(value, bool):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def sign(direction: float | None) -> int:
    """+1, -1, or 0 for a direction value (0 when null or zero)."""
    if direction is None or direction == 0:
        return 0
    return 1 if direction > 0 else -1
