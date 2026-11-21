# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Shared builders for the Factor 12 tests (S3-T14)."""

import copy
from pathlib import Path
from typing import Any

import yaml

from supertrends.scoring.config import ScoringConfig, load_scoring_config, parse_scoring_config

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"


def default_config() -> ScoringConfig:
    return load_scoring_config(CONFIG_PATH)


def config_with(**ripster_overrides: Any) -> ScoringConfig:
    """The shipped config with keys of the `ripster` block replaced."""
    data: dict[str, Any] = copy.deepcopy(yaml.safe_load(CONFIG_PATH.read_text()))
    data["ripster"].update(ripster_overrides)
    return parse_scoring_config(data)


def cloud(top: float, bot: float, direction: float, pos: float | None) -> dict[str, Any]:
    return {"top": top, "bot": bot, "dir": direction, "pos": pos}


def snapshot(
    *,
    bias: float | None = 0.0,
    c2_dir: float | None = 1.0,
    stack: float | None = 0.0,
    c3_dir: float | None = 1.0,
    c5_pos: float | None = 0.0,
    pullback: float | None = 0.0,
    bars_since_stack_flip: float | None = None,
    dir_w: float | None = 1.0,
    st_dir_d: float | None = 1.0,
    c3_top: float | None = 210.8,
    c3_bot: float | None = 206.3,
    c4: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A snapshot with the `ripster` block and the daily Supertrend direction.

    Defaults give trend +20 (c2 up) and mid +10 (c3 up) and nothing else, so one rule line is
    changed per test: the base score is 30.
    """
    return {
        "daily": {"supertrend": {"direction": st_dir_d}},
        "ripster": {
            "bias": bias,
            "stack": stack,
            "bars_since_stack_flip": bars_since_stack_flip,
            "pullback": pullback,
            "c2_dir": c2_dir,
            "c3_dir": c3_dir,
            "c3_top": c3_top,
            "c3_bot": c3_bot,
            "dir_w": dir_w,
            "clouds": {
                "c1": cloud(101.0, 99.0, 1.0, 1.0),
                "c2": cloud(105.0, 104.0, 1.0, 1.0),
                "c3": cloud(c3_top or 0.0, c3_bot or 0.0, c3_dir or 0.0, bias or 0.0),
                "c4": c4 or cloud(150.0, 140.0, 1.0, 1.0),
                "c5": cloud(180.0, 170.0, 1.0, c5_pos),
            },
        },
    }
