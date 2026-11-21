# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Shared helpers for the factor rule tests (S3-T02): config, context, and result checks."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from supertrends.scoring.config import ScoringConfig, load_scoring_config
from supertrends.scoring.factor import FactorContext, FactorResult

CONFIG = Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"
AS_OF = date(2026, 11, 13)


def load_cfg() -> ScoringConfig:
    return load_scoring_config(CONFIG)


def context(cfg: ScoringConfig) -> FactorContext:
    return FactorContext(config=cfg, as_of=AS_OF)


def evidence_by_name(result: FactorResult) -> dict[str, tuple[object, str, str]]:
    """Evidence as name -> (value, unit, reason); the names must be unique."""
    out: dict[str, tuple[object, str, str]] = {
        e.name: (e.value, e.unit, e.reason) for e in result.evidence
    }
    assert len(out) == len(result.evidence), "duplicate evidence names"
    return out
