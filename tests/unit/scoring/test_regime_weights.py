# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Regime classification and effective weights (TS-REG; S3-T05; FR-316 to FR-319).

Expected values are derived by hand from the spec tables, never from the code under test.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from supertrends.scoring.config import FACTOR_IDS, ScoringConfig
from supertrends.scoring.factor import Quality
from supertrends.scoring.regime import classify_regime, regime_multipliers
from supertrends.scoring.weights import NoScorableFactorsError, compute_weights
from tests.unit.scoring.cmp_support import load_cfg, make_results

# Spec "Regime multipliers" table, one row per factor: trending, ranging, transitional.
SPEC_TABLE: dict[str, tuple[float, float, float]] = {
    "supertrend": (1.25, 0.70, 1.00),
    "sma": (1.20, 0.70, 1.00),
    "macd": (1.10, 0.90, 1.00),
    "divergence": (0.90, 1.20, 1.00),
    "mean_reversion": (0.50, 1.60, 1.00),
    "fibonacci": (1.00, 1.10, 1.00),
    "levels": (0.90, 1.40, 1.00),
    "volatility": (1.00, 1.00, 1.00),
    "volume_osc": (1.00, 1.00, 1.00),
    "flow": (1.00, 1.00, 1.00),
    "fundamentals": (1.00, 1.00, 1.00),
    "ripster": (1.20, 0.70, 1.00),
}
BASE = {
    "supertrend": 20.0,
    "sma": 7.0,
    "macd": 8.0,
    "divergence": 9.0,
    "mean_reversion": 7.0,
    "fibonacci": 5.0,
    "levels": 7.0,
    "volatility": 4.0,
    "volume_osc": 6.0,
    "flow": 9.0,
    "fundamentals": 8.0,
    "ripster": 10.0,
}


@pytest.fixture(scope="module")
def cfg() -> ScoringConfig:
    return load_cfg()


@pytest.mark.parametrize(
    ("scenario", "adx", "expected"),
    [
        ("TS-REG-001", 25.0, "trending"),  # boundary: ADX >= 25
        ("TS-REG-001", 60.0, "trending"),
        ("TS-REG-002", 24.99, "transitional"),
        ("TS-REG-003", 20.0, "transitional"),  # ranging is strictly < 20
        ("TS-REG-004", 19.99, "ranging"),
        ("TS-REG-004", 0.0, "ranging"),
        ("TS-REG-102", None, "transitional"),  # warm-up: no ADX, no tilt
        ("TS-REG-102", math.nan, "transitional"),
    ],
)
def test_classify_regime_boundaries(
    cfg: ScoringConfig, scenario: str, adx: float | None, expected: str
) -> None:
    """TS-REG-001 to 004, TS-REG-102: ADX >= 25 trending, < 20 ranging, else transitional."""
    assert classify_regime(adx, cfg) == expected


def test_classify_regime_reads_thresholds_from_config(cfg: ScoringConfig) -> None:
    """TS-REG-103: thresholds are config values, not constants."""
    moved = cfg.model_copy(
        update={"regime": cfg.regime.model_copy(update={"trending_min": 30.0, "ranging_max": 10.0})}
    )
    assert classify_regime(25.0, moved) == "transitional"
    assert classify_regime(9.99, moved) == "ranging"
    assert classify_regime(30.0, moved) == "trending"


def test_base_weights_sum_to_100_and_match_spec(cfg: ScoringConfig) -> None:
    """TS-REG-005 and TS-REG-031: twelve base weights sum to 100; ripster 10, supertrend 20."""
    assert sum(BASE.values()) == 100.0  # hand check of the spec table
    detail = compute_weights(make_results(), cfg)
    assert dict(detail.base) == BASE
    assert detail.base["ripster"] == 10.0
    assert detail.base["supertrend"] == 20.0


@pytest.mark.parametrize("fid", FACTOR_IDS)
@pytest.mark.parametrize(
    ("column", "regime"), [(0, "trending"), (1, "ranging"), (2, "transitional")]
)
def test_multiplier_table_every_cell(
    cfg: ScoringConfig, fid: str, column: int, regime: str
) -> None:
    """TS-REG-007, 008, 009, 032: every cell of the multiplier table (trending, ranging, transitional)."""  # noqa: E501
    assert regime_multipliers(regime, cfg)[fid] == SPEC_TABLE[fid][column]


def test_multipliers_none_regime_is_all_ones(cfg: ScoringConfig) -> None:
    """TS-REG-029: Sprint 3 runs without a regime: every multiplier is 1.0."""
    assert dict(regime_multipliers(None, cfg)) == dict.fromkeys(FACTOR_IDS, 1.0)


def test_multipliers_unknown_regime_raises(cfg: ScoringConfig) -> None:
    """TS-REG-107: a regime name outside the three is a ValueError naming it."""
    with pytest.raises(ValueError, match="sideways"):
        regime_multipliers("sideways", cfg)


def test_trending_worked_example_pre_normalization_and_renormalized(cfg: ScoringConfig) -> None:
    """TS-REG-010: FR-318 worked example, trending, all present.

    Pre-normalization: 25, 8.4, 8.8, 8.1, 3.5, 5, 6.3, 4, 6, 9, 8, 12 = 104.1 (hand sum).
    Renormalized: supertrend 25/104.1*100 = 24.0154, ripster 12/104.1*100 = 11.5274.
    """
    detail = compute_weights(make_results(), cfg, regime="trending")
    expected_pre = {
        "supertrend": 25.0, "sma": 8.4, "macd": 8.8, "divergence": 8.1,
        "mean_reversion": 3.5, "fibonacci": 5.0, "levels": 6.3, "volatility": 4.0,
        "volume_osc": 6.0, "flow": 9.0, "fundamentals": 8.0, "ripster": 12.0,
    }  # fmt: skip
    for fid, value in expected_pre.items():
        assert detail.pre_normalization[fid] == pytest.approx(value, abs=1e-12)
    assert sum(detail.pre_normalization.values()) == pytest.approx(104.1, abs=1e-9)
    assert sum(detail.weights.values()) == pytest.approx(100.0, abs=1e-9)
    assert round(detail.weights["supertrend"], 2) == 24.02
    assert round(detail.weights["ripster"], 2) == 11.53
    assert "trending regime" in detail.adjustments


def test_ranging_regime_adjustment_and_transitional_none(cfg: ScoringConfig) -> None:
    """TS-REG-101: the adjustments list names the regime when it tilts, and is empty otherwise."""
    assert "ranging regime" in compute_weights(make_results(), cfg, regime="ranging").adjustments
    assert compute_weights(make_results(), cfg, regime="transitional").adjustments == ()
    assert compute_weights(make_results(), cfg, regime=None).adjustments == ()


@pytest.mark.parametrize(
    ("scenario", "days", "fund_pre", "fires"),
    [
        ("TS-REG-011", 5, 12.0, True),  # boundary: <= 5 days, 8 * 1.5
        ("TS-REG-011", 0, 12.0, True),
        ("TS-REG-012", 6, 8.0, False),  # boundary: 6 days, no change
        ("TS-REG-012", None, 8.0, False),
        ("TS-REG-108", -1, 8.0, False),  # an earnings date in the past is not an event
    ],
)
def test_event_adjustment_days_to_earnings(
    cfg: ScoringConfig, scenario: str, days: int | None, fund_pre: float, fires: bool
) -> None:
    """TS-REG-011, 012, 013, 108: earnings within 5 days multiply fundamentals by 1.5 and flag event_risk."""  # noqa: E501
    detail = compute_weights(make_results(), cfg, days_to_earnings=days)
    assert detail.pre_normalization["fundamentals"] == pytest.approx(fund_pre)
    assert detail.event_risk is fires
    assert any("earnings in" in a for a in detail.adjustments) is fires
    if fires:
        # transitional: only fundamentals moves, 104 total, 12/104*100 = 11.5385
        assert detail.weights["fundamentals"] == pytest.approx(1200 / 104, abs=1e-12)


def test_event_adjustment_text_and_order(cfg: ScoringConfig) -> None:
    """TS-REG-013, 014: text 'earnings in 3 days'; applied after the regime, before renormalizing.

    Trending, 3 days: regime sum 104.1, fundamentals 8 * 1.5 = 12 adds 4 -> 108.1 before
    renormalizing; fundamentals ends at 12/108.1*100 = 11.1008, supertrend 25/108.1*100 = 23.1267.
    """
    detail = compute_weights(make_results(), cfg, regime="trending", days_to_earnings=3)
    assert detail.adjustments == ("trending regime", "earnings in 3 days")
    assert sum(detail.pre_normalization.values()) == pytest.approx(108.1, abs=1e-9)
    assert detail.weights["fundamentals"] == pytest.approx(1200 / 108.1, abs=1e-12)
    assert detail.weights["supertrend"] == pytest.approx(2500 / 108.1, abs=1e-12)


def test_event_risk_flag_from_context_alone(cfg: ScoringConfig) -> None:
    """TS-REG-109: an injected event_risk flag is carried without any weight change."""
    detail = compute_weights(make_results(), cfg, event_risk=True)
    assert detail.event_risk is True
    assert detail.pre_normalization["fundamentals"] == 8.0
    assert detail.adjustments == ()


def test_missing_factor_redistributes_proportionally(cfg: ScoringConfig) -> None:
    """TS-REG-025: fundamentals missing (ETF): the other 92 points scale by 100/92.

    supertrend 20 * 100/92 = 21.7391, ripster 10 * 100/92 = 10.8696, fundamentals 0.
    """
    detail = compute_weights(make_results(missing=("fundamentals",)), cfg)
    assert detail.weights["fundamentals"] == 0.0
    assert detail.weights["supertrend"] == pytest.approx(2000 / 92, abs=1e-12)
    assert detail.weights["ripster"] == pytest.approx(1000 / 92, abs=1e-12)
    for fid in FACTOR_IDS:
        if fid != "fundamentals":
            assert detail.weights[fid] / BASE[fid] == pytest.approx(100 / 92, abs=1e-12)
    assert sum(detail.weights.values()) == pytest.approx(100.0, abs=1e-9)
    assert "fundamentals missing" in " ".join(detail.adjustments)


def test_degraded_fundamentals_weight_halved_then_renormalized(cfg: ScoringConfig) -> None:
    """TS-REG-026: fundamentals older than 120 days: multiplier 0.5, so 4 of 96, 4/96*100 = 4.1667."""  # noqa: E501
    results = make_results(
        qualities={"fundamentals": Quality.DEGRADED}, multipliers={"fundamentals": 0.5}
    )
    detail = compute_weights(results, cfg)
    assert detail.pre_normalization["fundamentals"] == 4.0
    assert detail.weights["fundamentals"] == pytest.approx(400 / 96, abs=1e-12)
    assert detail.weights["supertrend"] == pytest.approx(2000 / 96, abs=1e-12)
    assert any("fundamentals" in a and "0.50" in a for a in detail.adjustments)


def test_daily_estimate_flow_multiplier_then_renormalized(cfg: ScoringConfig) -> None:
    """TS-REG-027: flow 9 * 0.6 = 5.4; total 96.4; flow 540/96.4 = 5.6017, supertrend 2000/96.4 = 20.7469."""  # noqa: E501
    results = make_results(qualities={"flow": Quality.DAILY_ESTIMATE}, multipliers={"flow": 0.6})
    detail = compute_weights(results, cfg)
    assert detail.pre_normalization["flow"] == pytest.approx(5.4, abs=1e-12)
    assert detail.weights["flow"] == pytest.approx(540 / 96.4, abs=1e-12)
    assert detail.weights["supertrend"] == pytest.approx(2000 / 96.4, abs=1e-12)


def test_all_but_one_factor_missing_remaining_weight_100(cfg: ScoringConfig) -> None:
    """TS-REG-028: one factor left carries the whole 100."""
    others = tuple(f for f in FACTOR_IDS if f != "ripster")
    detail = compute_weights(make_results(missing=others), cfg)
    assert detail.weights["ripster"] == pytest.approx(100.0, abs=1e-12)
    assert sum(detail.weights.values()) == pytest.approx(100.0, abs=1e-12)


def test_sprint3_defaults_multipliers_one_fundamentals_missing(cfg: ScoringConfig) -> None:
    """TS-REG-029: no regime injected and fundamentals missing: multipliers 1.0, weights are base * 100/92."""  # noqa: E501
    detail = compute_weights(make_results(missing=("fundamentals",)), cfg)
    assert dict(detail.regime_multipliers) == dict.fromkeys(FACTOR_IDS, 1.0)
    assert detail.weights["sma"] == pytest.approx(700 / 92, abs=1e-12)
    # the injected-regime path exists on the same call
    trending = compute_weights(make_results(missing=("fundamentals",)), cfg, regime="trending")
    assert trending.regime_multipliers["supertrend"] == 1.25


def test_all_missing_raises(cfg: ScoringConfig) -> None:
    """TS-REG-105: no scorable factor: NoScorableFactorsError (a ValueError), not a zero composite."""  # noqa: E501
    with pytest.raises(NoScorableFactorsError):
        compute_weights(make_results(missing=FACTOR_IDS), cfg)
    assert issubclass(NoScorableFactorsError, ValueError)


def test_results_must_cover_exactly_the_factor_ids(cfg: ScoringConfig) -> None:
    """TS-REG-104: a missing, extra or mislabelled result is a ValueError, never silently dropped."""  # noqa: E501
    results = make_results()
    short = {k: v for k, v in results.items() if k != "macd"}
    with pytest.raises(ValueError, match="macd"):
        compute_weights(short, cfg)
    with pytest.raises(ValueError, match="bogus"):
        compute_weights({**results, "bogus": results["macd"]}, cfg)
    with pytest.raises(ValueError, match="sma"):
        compute_weights({**results, "sma": results["macd"]}, cfg)


def test_weight_result_is_frozen_and_immutable(cfg: ScoringConfig) -> None:
    """TS-REG-106: WeightResult is frozen and its mappings are read-only."""
    detail = compute_weights(make_results(), cfg)
    with pytest.raises(AttributeError):
        detail.event_risk = True  # type: ignore[misc]
    with pytest.raises(TypeError):
        detail.weights["sma"] = 1.0  # type: ignore[index]


@settings(max_examples=150, deadline=None)
@given(
    regime=st.sampled_from([None, "trending", "ranging", "transitional"]),
    days=st.one_of(st.none(), st.integers(min_value=-3, max_value=30)),
    missing=st.sets(st.sampled_from(FACTOR_IDS), max_size=len(FACTOR_IDS) - 1),
    mults=st.dictionaries(
        st.sampled_from(FACTOR_IDS), st.floats(min_value=0.1, max_value=1.0), max_size=4
    ),
)
def test_weights_always_sum_to_100(
    regime: str | None,
    days: int | None,
    missing: set[str],
    mults: dict[str, float],
) -> None:
    """TS-REG-024: every combination of regime, event, quality multipliers and missing factors sums to 100."""  # noqa: E501
    cfg = load_cfg()
    results = make_results(missing=tuple(missing), multipliers=mults)
    detail = compute_weights(results, cfg, regime=regime, days_to_earnings=days)
    assert sum(detail.weights.values()) == pytest.approx(100.0, abs=1e-9)
    assert all(detail.weights[m] == 0.0 for m in missing)
    assert all(w >= 0 for w in detail.weights.values())
