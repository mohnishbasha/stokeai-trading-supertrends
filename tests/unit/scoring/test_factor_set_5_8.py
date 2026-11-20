# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factors 5 to 8 together (S3-T03): purity, registry membership, declared inputs."""

import copy
import json
from datetime import date
from pathlib import Path

import pytest

from supertrends.scoring.config import ScoringConfig, load_scoring_config
from supertrends.scoring.factor import FactorContext, expand_input_paths, get_path
from supertrends.scoring.factors import default_registry
from supertrends.scoring.snapshot import compute_snapshot
from tests.unit.indicators.lookahead_support import make_bundle

CONFIG = Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"
IDS = ("mean_reversion", "fibonacci", "levels", "volatility")


@pytest.fixture(scope="module")
def cfg() -> ScoringConfig:
    return load_scoring_config(CONFIG)


@pytest.mark.parametrize("factor_id", IDS)
def test_unit_factors_5_to_8_are_pure_and_deterministic(cfg: ScoringConfig, factor_id: str) -> None:
    """TS-SCR-390: same snapshot, same result; the snapshot is not mutated; the result is JSON."""
    bundle = make_bundle(seed=11, n=400, intraday_from=None)
    doc = compute_snapshot(bundle, cfg, date.fromisoformat(str(bundle.dates[-1])))
    before = copy.deepcopy(doc)
    ctx = FactorContext(config=cfg, as_of=date(2026, 1, 2))
    factor = default_registry().get(factor_id)
    first = factor.compute(doc, ctx)
    second = factor.compute(doc, ctx)
    assert first == second
    assert doc == before
    assert first.factor_id == factor_id
    json.dumps(first.model_dump(mode="json"), allow_nan=False)
    assert all(e.reason and e.unit for e in first.evidence)


@pytest.mark.parametrize("factor_id", IDS)
def test_unit_factors_5_to_8_read_only_declared_inputs(cfg: ScoringConfig, factor_id: str) -> None:
    """TS-SCR-391: removing every undeclared snapshot key changes nothing (inputs are declared)."""
    bundle = make_bundle(seed=12, n=400, intraday_from=None)
    doc = compute_snapshot(bundle, cfg, date.fromisoformat(str(bundle.dates[-1])))
    factor = default_registry().get(factor_id)
    paths = expand_input_paths(factor.input_paths, cfg)
    kept: dict = {}
    for path in paths:
        node = kept
        parts = path.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = get_path(doc, path)
    ctx = FactorContext(config=cfg, as_of=date(2026, 1, 2))
    assert factor.compute(kept, ctx) == factor.compute(doc, ctx)
