# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Shared builders for the regime, weights, composite and confidence tests (S3-T05)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from supertrends.scoring.config import FACTOR_IDS, ScoringConfig, load_scoring_config
from supertrends.scoring.factor import FactorContext, FactorResult, Quality

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"
AS_OF = date(2026, 3, 2)


def load_cfg() -> ScoringConfig:
    return load_scoring_config(CONFIG_PATH)


def make_results(
    scores: Mapping[str, float] | None = None,
    *,
    default: float = 0.0,
    missing: tuple[str, ...] = (),
    qualities: Mapping[str, Quality] | None = None,
    multipliers: Mapping[str, float] | None = None,
) -> dict[str, FactorResult]:
    """One FactorResult per factor ID; `scores` overrides `default`."""
    scores = scores or {}
    qualities = qualities or {}
    multipliers = multipliers or {}
    out: dict[str, FactorResult] = {}
    for fid in FACTOR_IDS:
        if fid in missing:
            out[fid] = FactorResult.missing(fid, reason=f"{fid} data not available")
        else:
            out[fid] = FactorResult(
                factor_id=fid,
                score=scores.get(fid, default),
                quality=qualities.get(fid, Quality.OK),
                weight_multiplier=multipliers.get(fid, 1.0),
            )
    return out


def make_snapshot(
    *,
    adx: float | None = 22.0,
    atr_pct_rank: float | None = 50.0,
    st_dir_d: float | None = 1.0,
    st_dir_w: float | None = 1.0,
    rc_stack: float | None = 1.0,
) -> dict[str, Any]:
    """The snapshot paths the regime and confidence rules read (factor.*_INPUT_PATHS)."""
    return {
        "daily": {
            "adx": {"adx": adx},
            "atr_pct_rank": atr_pct_rank,
            "supertrend": {"direction": st_dir_d},
        },
        "weekly": {"supertrend_direction": st_dir_w},
        "ripster": {"stack": rc_stack},
    }


def make_context(cfg: ScoringConfig, **over: Any) -> FactorContext:
    return FactorContext(config=cfg, as_of=AS_OF, **over)
