# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Ripster rules outside the factor score (Signal Engine Specification, Factor 12; S3-T14).

Stub: every function raises NotImplementedError("S3-T14") until the implementation commit.
"""

from collections.abc import Mapping
from typing import Any, Literal

from supertrends.scoring.config import ScoringConfig

Side = Literal["buy", "sell"]


def confidence_stack_penalty(snapshot: Mapping[str, Any], config: ScoringConfig) -> float:
    raise NotImplementedError("S3-T14")


def selection_bias_gate(
    snapshot: Mapping[str, Any], side: Side, config: ScoringConfig
) -> tuple[bool, str | None]:
    raise NotImplementedError("S3-T14")


def ripster_evidence(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("S3-T14")
