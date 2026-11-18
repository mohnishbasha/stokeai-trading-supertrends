# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor registry and the twelve stub factors (S3-T01; ARCHITECTURE section 2, 13.2)."""

import importlib
import subprocess
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from supertrends.scoring.config import FACTOR_IDS, ScoringConfig, load_scoring_config
from supertrends.scoring.factor import (
    Factor,
    FactorContext,
    FactorRegistry,
    FactorResult,
    Quality,
)
from supertrends.scoring.factors import ALL_FACTORS, OWNER_TASKS, default_registry

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "config" / "scoring.yaml"

# Owner task of every stub, from the Sprint 3 plan: the message of its NotImplementedError.
EXPECTED_OWNERS = {
    "supertrend": "S3-T02",
    "sma": "S3-T02",
    "macd": "S3-T02",
    "divergence": "S3-T02",
    "mean_reversion": "S3-T03",
    "fibonacci": "S3-T03",
    "levels": "S3-T03",
    "volatility": "S3-T03",
    "volume_osc": "S3-T04",
    "flow": "S3-T04",
    "ripster": "S3-T14",
}


@pytest.fixture(scope="module")
def cfg() -> ScoringConfig:
    return load_scoring_config(CONFIG)


@pytest.fixture
def ctx(cfg: ScoringConfig) -> FactorContext:
    return FactorContext(config=cfg, as_of=date(2026, 11, 13))


class _Fake:
    def __init__(self, factor_id: str) -> None:
        self.id = factor_id
        self.input_paths: tuple[str, ...] = ()

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        return FactorResult.missing(self.id, reason="fake")


def test_unit_factor_registry_every_config_factor_id_registered_and_reverse(
    cfg: ScoringConfig,
) -> None:
    """TS-SCR-003: config weight ids and registered factor ids match both ways."""
    registry = default_registry()
    assert set(registry.ids()) == set(cfg.weights.as_dict())
    assert set(cfg.weights.as_dict()) == set(FACTOR_IDS)
    assert len(registry) == 12
    registry.validate_against(cfg)  # does not raise


def test_unit_factor_registry_ordered_iteration_matches_config_weight_order(
    cfg: ScoringConfig,
) -> None:
    """TS-SCR-306: `ordered(config)` yields the factors in the order of `weights`."""
    ordered = default_registry().ordered(cfg)
    assert [f.id for f in ordered] == list(cfg.weights.as_dict())
    assert [f.id for f in ordered] == [
        "supertrend",
        "sma",
        "macd",
        "divergence",
        "mean_reversion",
        "fibonacci",
        "levels",
        "volatility",
        "volume_osc",
        "flow",
        "fundamentals",
        "ripster",
    ]


def test_unit_factor_registry_ordered_ignores_registration_order(cfg: ScoringConfig) -> None:
    """TS-SCR-306: registration order does not matter; config order wins."""
    registry = FactorRegistry()
    for fid in reversed(FACTOR_IDS):
        registry.register(_Fake(fid))
    assert registry.ids() == tuple(reversed(FACTOR_IDS))
    assert [f.id for f in registry.ordered(cfg)] == list(FACTOR_IDS)


def test_unit_factor_registry_get_returns_the_registered_factor() -> None:
    """TS-SCR-307: get by id; unknown id raises KeyError listing the known ids."""
    registry = default_registry()
    assert registry.get("ripster").id == "ripster"
    assert "ripster" in registry
    assert "vibes" not in registry
    with pytest.raises(KeyError, match="vibes"):
        registry.get("vibes")


def test_unit_factor_registry_rejects_duplicate_and_empty_ids() -> None:
    """TS-SCR-307: one factor per id; ids are non-empty."""
    registry = FactorRegistry()
    registry.register(_Fake("sma"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_Fake("sma"))
    with pytest.raises(ValueError, match="id"):
        registry.register(_Fake(""))


def test_unit_factor_registry_validate_names_every_mismatch_in_both_directions(
    cfg: ScoringConfig,
) -> None:
    """TS-SCR-003: a missing registration and an extra registration are both reported."""
    registry = FactorRegistry()
    for fid in FACTOR_IDS:
        if fid != "flow":
            registry.register(_Fake(fid))
    registry.register(_Fake("vibes"))
    with pytest.raises(ValueError) as err:  # noqa: PT011 - both messages are asserted below
        registry.validate_against(cfg)
    assert "flow" in str(err.value)
    assert "vibes" in str(err.value)
    with pytest.raises(ValueError, match="flow"):
        registry.ordered(cfg)


def test_unit_factor_registry_every_factor_satisfies_the_protocol() -> None:
    """TS-SCR-307: id, input_paths and compute exist on every registered factor."""
    for factor in default_registry():
        assert isinstance(factor, Factor)
        assert isinstance(factor.id, str)
        assert isinstance(factor.input_paths, tuple)
        assert callable(factor.compute)


def test_unit_factors_all_factors_has_one_entry_per_config_id_in_config_order() -> None:
    """TS-SCR-318: the explicit list, not import side effects, defines the registry."""
    assert [f.id for f in ALL_FACTORS] == list(FACTOR_IDS)
    assert set(OWNER_TASKS) == set(FACTOR_IDS)


@pytest.mark.parametrize("module_name", FACTOR_IDS)
def test_unit_factors_one_module_per_factor_id_exposes_its_factor(module_name: str) -> None:
    """TS-SCR-318: `supertrends.scoring.factors.<id>` exists and exposes FACTOR and INPUT_PATHS."""
    module = importlib.import_module(f"supertrends.scoring.factors.{module_name}")
    assert module.FACTOR.id == module_name
    assert module.FACTOR.input_paths == module.INPUT_PATHS
    assert module.__doc__
    assert module.FACTOR in ALL_FACTORS


def test_unit_factors_registry_is_complete_in_a_fresh_interpreter_without_other_imports() -> None:
    """TS-SCR-318: importing only the package gives all twelve factors (no skipped side effects)."""
    code = (
        "from supertrends.scoring.factors import default_registry;"
        "print(','.join(default_registry().ids()))"
    )
    out = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip().split(",") == list(FACTOR_IDS)


@pytest.mark.parametrize(("factor_id", "task"), sorted(EXPECTED_OWNERS.items()))
def test_unit_factor_stub_raises_not_implemented_naming_its_owner_task(
    factor_id: str, task: str, ctx: FactorContext
) -> None:
    """TS-SCR-307: each stub raises NotImplementedError whose message is the owning task."""
    assert OWNER_TASKS[factor_id] == task
    with pytest.raises(NotImplementedError) as err:
        default_registry().get(factor_id).compute({}, ctx)
    assert str(err.value) == task


def test_unit_factor_fundamentals_stub_returns_missing_with_score_zero(ctx: FactorContext) -> None:
    """TS-SCR-308: Sprint 3 has no fundamentals; the factor is missing, score 0, weight dropped."""
    res = default_registry().get("fundamentals").compute({}, ctx)
    assert res.factor_id == "fundamentals"
    assert res.quality is Quality.MISSING
    assert res.is_missing
    assert res.score == 0
    assert res.weight_multiplier == 1.0
    assert res.evidence
    assert res.reasons == ("Fundamentals are not available for this ticker",)


def test_unit_factor_fundamentals_stub_ignores_snapshot_and_injected_fundamentals(
    cfg: ScoringConfig,
) -> None:
    """TS-SCR-308: even with injected fundamentals the Sprint 3 factor stays missing."""
    ctx = FactorContext(
        config=cfg, as_of=date(2026, 11, 13), fundamentals={"revenue_growth_yoy": 0.3}
    )
    res = default_registry().get("fundamentals").compute({"daily": {"close": 1.0}}, ctx)
    assert res.is_missing


def test_unit_factor_owner_tasks_cover_every_stub_and_name_s3_tasks() -> None:
    """TS-SCR-307: every factor except fundamentals names an S3 task; fundamentals names S5."""
    assert {k: v for k, v in OWNER_TASKS.items() if k != "fundamentals"} == EXPECTED_OWNERS
    assert OWNER_TASKS["fundamentals"] == "S5-T04"
