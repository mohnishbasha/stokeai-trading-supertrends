# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Scoring config at spec 1.1.0 (S3-T01; BUILD_PROMPT Appendix E, ARCHITECTURE section 13)."""

import copy
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from supertrends.errors import ConfigError
from supertrends.scoring.config import (
    FACTOR_IDS,
    ScoringConfig,
    load_scoring_config,
    parse_scoring_config,
)

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "config" / "scoring.yaml"
VERSION_LINE = re.compile(r"^  version: \d+$")


def _yaml_block_after(text: str, heading: str) -> str:
    """The first fenced yaml block after `heading` in a Markdown document."""
    after = text.split(heading, 1)[1]
    match = re.search(r"```yaml\n(.*?)\n```", after, flags=re.DOTALL)
    assert match, heading
    return match.group(1)


def _meaningful_lines(text: str) -> list[str]:
    """Lines of a YAML document without comments and blank lines (diff ignoring comments)."""
    return [
        ln.rstrip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")
    ]


def _with_version(lines: list[str], version: int) -> list[str]:
    return [f"  version: {version}" if VERSION_LINE.match(ln) else ln for ln in lines]


@pytest.fixture(scope="module")
def raw() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(CONFIG.read_text())
    return data


def test_unit_config_equals_appendix_e_ignoring_comments_and_the_version_bump() -> None:
    """TS-SCR-301: config/scoring.yaml is BUILD_PROMPT Appendix E line for line (spec 1.1.0)."""
    appendix = _yaml_block_after((ROOT / "BUILD_PROMPT.md").read_text(), "## Appendix E")
    expected = _with_version(_meaningful_lines(appendix), 2)
    assert _meaningful_lines(CONFIG.read_text()) == expected


def test_unit_config_scoring_version_is_2_for_spec_1_1_0() -> None:
    """TS-SCR-302: the Ripster weights and block are a scoring change, so version is 2."""
    assert load_scoring_config(CONFIG).scoring.version == 2


def test_unit_config_architecture_13_1_mirrors_the_config_file() -> None:
    """TS-SCR-317: the yaml in ARCHITECTURE 13.1 equals config/scoring.yaml, comments ignored."""
    block = _yaml_block_after((ROOT / "docs" / "ARCHITECTURE.md").read_text(), "### 13.1")
    assert _meaningful_lines(block) == _meaningful_lines(CONFIG.read_text())


def test_unit_config_ripster_block_values_match_appendix_e() -> None:
    """TS-SCR-303: the ripster block is parsed into typed values."""
    cfg = load_scoring_config(CONFIG)
    r = cfg.ripster
    assert (r.source, r.ma_type) == ("hl2", "ema")
    assert r.clouds.pairs() == ((8, 9), (5, 12), (34, 50), (72, 89), (180, 200))
    assert r.points.model_dump() == {
        "bias": 30,
        "trend": 20,
        "stack": 20,
        "mid": 10,
        "long": 10,
        "pullback": 10,
    }
    assert r.pullback_lookback_bars == 3
    assert r.confidence_stack_conflict_penalty == 10
    assert r.selection_bias_gate is True
    # the six scored components add up to the full score range
    assert sum(r.points.model_dump().values()) == 100


def _drop(path: tuple[str, ...]) -> Callable[[dict[str, Any]], None]:
    def go(d: dict[str, Any]) -> None:
        node = d
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]

    return go


def _set(path: tuple[str, ...], value: Any) -> Callable[[dict[str, Any]], None]:
    def go(d: dict[str, Any]) -> None:
        node = d
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return go


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (_drop(("ripster", "points")), "ripster.points"),
        (_set(("ripster", "surprise"), 1), "ripster.surprise"),
        (_set(("ripster", "clouds", "c6"), [1, 2]), "ripster.clouds.c6"),
        (_set(("ripster", "clouds", "c3"), [50, 34]), "ripster.clouds"),
        (_set(("ripster", "source"), "close"), "ripster.source"),
        (_set(("ripster", "ma_type"), "sma"), "ripster.ma_type"),
        (_set(("ripster", "pullback_lookback_bars"), 0), "pullback_lookback_bars"),
        (_set(("ripster", "points", "bias"), -1), "ripster.points.bias"),
        (_drop(("weights", "ripster")), "weights.ripster"),
        (_set(("regime", "multipliers", "trending", "vibes"), 1), "vibes"),
    ],
)
def test_unit_config_ripster_block_is_strict(
    raw: dict[str, Any], mutate: Callable[[dict[str, Any]], None], needle: str
) -> None:
    """TS-SCR-304: unknown, missing or out-of-range ripster keys are rejected naming the key."""
    data = copy.deepcopy(raw)
    mutate(data)
    with pytest.raises(ConfigError, match=re.escape(needle)):
        parse_scoring_config(data)


def test_unit_config_twelve_factor_ids_in_weights_order_and_regime_multipliers_cover_ripster() -> (
    None
):
    """TS-SCR-305: FACTOR_IDS, weights and regime multipliers all carry the twelve factors."""
    cfg = load_scoring_config(CONFIG)
    assert len(FACTOR_IDS) == 12
    assert FACTOR_IDS[-1] == "ripster"
    assert tuple(cfg.weights.as_dict()) == FACTOR_IDS
    assert isinstance(cfg, ScoringConfig)
    assert cfg.regime.multipliers["trending"]["ripster"] == 1.20
    assert cfg.regime.multipliers["ranging"]["ripster"] == 0.70
    assert cfg.regime.multipliers["transitional"]["ripster"] == 1.00
