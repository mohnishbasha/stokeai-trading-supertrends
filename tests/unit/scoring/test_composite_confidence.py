# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Composite, display, bands, confidence and the score card (TS-CMP; S3-T05; FR-324 to FR-335).

Expected values are derived by hand (stated in each comment), never from the code under test.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from supertrends.scoring.composite import (
    Band,
    assign_band,
    compute_composite,
    display_score,
    score_ticker,
)
from supertrends.scoring.confidence import compute_confidence
from supertrends.scoring.config import FACTOR_IDS, ScoringConfig
from supertrends.scoring.factor import Quality
from supertrends.scoring.weights import NoScorableFactorsError, compute_weights
from tests.unit.scoring.cmp_support import (
    load_cfg,
    make_context,
    make_results,
    make_snapshot,
)


@pytest.fixture(scope="module")
def cfg() -> ScoringConfig:
    return load_cfg()


# Hand example used by several tests: fundamentals missing (92 points left), scores below.
# sum(w*s) = 1600+420+320-180+70+0-210+200+420-540+900 = 3000, composite = 3000/92 = 32.6087.
EXAMPLE_SCORES = {
    "supertrend": 80.0, "sma": 60.0, "macd": 40.0, "divergence": -20.0, "mean_reversion": 10.0,
    "fibonacci": 0.0, "levels": -30.0, "volatility": 50.0, "volume_osc": 70.0, "flow": -60.0,
    "ripster": 90.0,
}  # fmt: skip


def _conf(
    cfg: ScoringConfig,
    results: dict[str, Any],
    snapshot: dict[str, Any] | None = None,
    *,
    event_risk: bool = False,
) -> Any:
    weights = compute_weights(results, cfg).weights
    composite = compute_composite(results, weights).composite
    return compute_confidence(
        snapshot or make_snapshot(), results, weights, composite, cfg, event_risk=event_risk
    )


def test_composite_weighted_mean_over_non_missing(cfg: ScoringConfig) -> None:
    """TS-CMP-001: sum(w*s)/sum(w): supertrend 50 (20) and ripster -10 (10), rest missing: 900/30 = 30."""  # noqa: E501
    others = tuple(f for f in FACTOR_IDS if f not in ("supertrend", "ripster"))
    results = make_results({"supertrend": 50.0, "ripster": -10.0}, missing=others)
    weights = compute_weights(results, cfg).weights
    assert compute_composite(results, weights).composite == pytest.approx(30.0, abs=1e-9)


def test_contributions_sum_to_composite(cfg: ScoringConfig) -> None:
    """TS-CMP-002: contribution = weight*score/100; they sum to the composite within 1e-9."""
    results = make_results(EXAMPLE_SCORES, missing=("fundamentals",))
    weights = compute_weights(results, cfg).weights
    out = compute_composite(results, weights)
    assert abs(sum(out.contributions.values()) - out.composite) < 1e-9
    assert out.composite == pytest.approx(3000 / 92, abs=1e-12)
    for fid, score in EXAMPLE_SCORES.items():
        assert out.contributions[fid] == pytest.approx(weights[fid] * score / 100, abs=1e-12)
    assert out.contributions["fundamentals"] == 0.0
    # supertrend: 20 * 100/92 * 80 / 100 = 17.3913
    assert out.contributions["supertrend"] == pytest.approx(1600 / 92, abs=1e-12)


def test_removing_a_factor_redistributes_weight_proportionally(cfg: ScoringConfig) -> None:
    """TS-CMP-003: dropping fundamentals (8 of 100) scales every other weight by 100/92."""
    full = compute_weights(make_results(EXAMPLE_SCORES, default=10.0), cfg).weights
    cut = compute_weights(
        make_results(EXAMPLE_SCORES, default=10.0, missing=("fundamentals",)), cfg
    ).weights
    for fid in FACTOR_IDS:
        if fid != "fundamentals":
            assert cut[fid] / full[fid] == pytest.approx(100 / 92, abs=1e-12)
    assert cut["fundamentals"] == 0.0


@pytest.mark.parametrize(
    ("scenario", "composite", "expected"),
    [
        ("TS-CMP-004", 0.0, 50.0),
        ("TS-CMP-005", 100.0, 100.0),
        ("TS-CMP-006", -100.0, 0.0),
        ("TS-CMP-007", 56.8, 78.4),  # FR-325 example: (56.8+100)/2 = 78.4
        # exact binary halves: (-99.5+100)/2 = 0.25 -> half to even 0.2; (-98.5+100)/2 = 0.75 -> 0.8
        ("TS-CMP-007", -99.5, 0.2),
        ("TS-CMP-007", -98.5, 0.8),
        ("TS-CMP-007", 3000 / 92, 66.3),  # (32.6087+100)/2 = 66.304
    ],
)
def test_display_score(scenario: str, composite: float, expected: float) -> None:
    """TS-CMP-004 to 007: round((composite + 100) / 2, 1); round half to even on the double."""
    assert display_score(composite) == expected


def test_display_score_is_clamped_to_0_100() -> None:
    """TS-CMP-007: float noise past the ends cannot leave 0..100."""
    assert display_score(100.00000000001) == 100.0
    assert display_score(-100.00000000001) == 0.0


BAND_CASES = [
    ("TS-CMP-008", 80.0, Band.STRONG_BUY),
    ("TS-CMP-008", 100.0, Band.STRONG_BUY),
    ("TS-CMP-009", 79.9, Band.BUY),
    ("TS-CMP-010", 65.0, Band.BUY),
    ("TS-CMP-011", 64.9, Band.NEUTRAL_UP),
    ("TS-CMP-012", 50.0, Band.NEUTRAL_UP),
    ("TS-CMP-013", 49.9, Band.NEUTRAL_DOWN),
    ("TS-CMP-014", 35.1, Band.NEUTRAL_DOWN),
    ("TS-CMP-015", 35.0, Band.SELL),
    ("TS-CMP-016", 20.1, Band.SELL),
    ("TS-CMP-017", 20.0, Band.STRONG_SELL),
    ("TS-CMP-018", 0.0, Band.STRONG_SELL),
]


@pytest.mark.parametrize(("scenario", "display", "band"), BAND_CASES)
def test_band_boundaries(cfg: ScoringConfig, scenario: str, display: float, band: Band) -> None:
    """TS-CMP-008 to 018: every boundary of the band table (FR-326)."""
    assert assign_band(display, cfg) == band


def test_band_labels_match_spec() -> None:
    """TS-CMP-110: the band strings are the spec's labels."""
    assert [b.value for b in Band] == [
        "Strong Buy", "Buy", "Neutral, leaning up", "Neutral, leaning down", "Sell", "Strong Sell",
    ]  # fmt: skip


def test_band_every_display_value_maps_to_exactly_one_band(cfg: ScoringConfig) -> None:
    """TS-CMP-019: 0.0 to 100.0 step 0.1 each fall in exactly one spec interval, and assign_band agrees."""  # noqa: E501
    # Intervals in tenths from the spec table: contiguous, no gaps, no overlaps.
    intervals = [
        (0, 200, Band.STRONG_SELL),
        (201, 350, Band.SELL),
        (351, 499, Band.NEUTRAL_DOWN),
        (500, 649, Band.NEUTRAL_UP),
        (650, 799, Band.BUY),
        (800, 1000, Band.STRONG_BUY),
    ]
    for tenth in range(1001):
        hits = [band for lo, hi, band in intervals if lo <= tenth <= hi]
        assert len(hits) == 1
        assert assign_band(round(tenth / 10, 1), cfg) == hits[0]


def test_band_edges_follow_config_thresholds(cfg: ScoringConfig) -> None:
    """TS-CMP-111: the Buy floor and Sell ceiling come from thresholds.buy_display_min and sell_display_max."""  # noqa: E501
    moved = cfg.model_copy(
        update={
            "thresholds": cfg.thresholds.model_copy(
                update={"buy_display_min": 70.0, "sell_display_max": 30.0}
            )
        }
    )
    assert assign_band(69.9, moved) == Band.NEUTRAL_UP
    assert assign_band(70.0, moved) == Band.BUY
    assert assign_band(30.0, moved) == Band.SELL
    assert assign_band(30.1, moved) == Band.NEUTRAL_DOWN


def _split_results(
    negative: tuple[str, ...], pos: float = 50.0, neg: float = -10.0, **kw: Any
) -> dict[str, Any]:
    """Scores: factors in `negative` get `neg`, every other factor `pos`."""
    scores = {fid: (neg if fid in negative else pos) for fid in FACTOR_IDS}
    return make_results(scores, **kw)


def test_confidence_agreement_is_share_of_weight_with_composite_sign(cfg: ScoringConfig) -> None:
    """TS-CMP-020: supertrend (20 of 100) negative, rest positive: composite (80*50-20*10)/100 = 38 > 0, agreement 0.80."""  # noqa: E501
    out = _conf(cfg, _split_results(("supertrend",)))
    assert out.agreement == pytest.approx(0.80, abs=1e-12)
    assert out.value == pytest.approx(80.0, abs=1e-9)
    assert out.deductions == ()


def test_confidence_all_agree_is_100(cfg: ScoringConfig) -> None:
    """TS-CMP-021: all factors positive and no penalty fires gives 100."""
    out = _conf(cfg, make_results(default=30.0))
    assert out.agreement == pytest.approx(1.0, abs=1e-12)
    assert out.value == pytest.approx(100.0, abs=1e-9)


@pytest.mark.parametrize(
    ("rank", "points"),
    [(95.0, 15.0), (90.01, 15.0), (90.0, 0.0), (None, 0.0)],  # boundary: strictly > 90
)
def test_confidence_atr_rank_above_90(
    cfg: ScoringConfig, rank: float | None, points: float
) -> None:
    """TS-CMP-022: atr_pct_rank > 90 subtracts 15 (exactly 90 and a warm-up null do not)."""
    out = _conf(cfg, make_results(default=30.0), make_snapshot(atr_pct_rank=rank))
    assert out.value == pytest.approx(100.0 - points, abs=1e-9)
    assert [d.code for d in out.deductions] == (["atr_pct_rank"] if points else [])


def test_confidence_degraded_subtracts_10(cfg: ScoringConfig) -> None:
    """TS-CMP-023: any degraded factor: 100 - 10 = 90."""
    results = make_results(default=30.0, qualities={"fundamentals": Quality.DEGRADED})
    out = _conf(cfg, results)
    assert out.value == pytest.approx(90.0, abs=1e-9)
    assert [d.code for d in out.deductions] == ["degraded"]


def test_confidence_daily_estimate_is_not_degraded(cfg: ScoringConfig) -> None:
    """TS-CMP-112: the Factor 10 daily estimate is its own quality; only degraded costs 10."""
    results = make_results(default=30.0, qualities={"flow": Quality.DAILY_ESTIMATE})
    assert _conf(cfg, results).value == pytest.approx(100.0, abs=1e-9)


@pytest.mark.parametrize(
    ("st_d", "st_w", "points"),
    [(1.0, -1.0, 10.0), (-1.0, 1.0, 10.0), (1.0, 1.0, 0.0), (-1.0, -1.0, 0.0), (1.0, None, 0.0)],
)
def test_confidence_weekly_disagreement(
    cfg: ScoringConfig, st_d: float, st_w: float | None, points: float
) -> None:
    """TS-CMP-024: st_dir_w != st_dir_d subtracts 10; an unknown weekly direction (null) does not."""  # noqa: E501
    snap = make_snapshot(st_dir_d=st_d, st_dir_w=st_w, rc_stack=st_d)
    out = _conf(cfg, make_results(default=30.0), snap)
    assert out.value == pytest.approx(100.0 - points, abs=1e-9)


def test_confidence_event_risk_subtracts_10(cfg: ScoringConfig) -> None:
    """TS-CMP-025: event_risk: 100 - 10 = 90."""
    out = _conf(cfg, make_results(default=30.0), event_risk=True)
    assert out.value == pytest.approx(90.0, abs=1e-9)
    assert [d.code for d in out.deductions] == ["event_risk"]


def _all_penalties(cfg: ScoringConfig, results: dict[str, Any]) -> Any:
    results["fundamentals"] = results["fundamentals"].model_copy(
        update={"quality": Quality.DEGRADED}
    )
    snap = make_snapshot(atr_pct_rank=95.0, st_dir_d=1.0, st_dir_w=-1.0, rc_stack=-1.0)
    return _conf(cfg, results, snap, event_risk=True)


def test_confidence_all_penalties_stack_55(cfg: ScoringConfig) -> None:
    """TS-CMP-026: 15 + 10 + 10 + 10 + 10 = 55 off agreement 1.0: 100 - 55 = 45, five deductions listed."""  # noqa: E501
    out = _all_penalties(cfg, make_results(default=30.0))
    assert out.value == pytest.approx(45.0, abs=1e-9)
    assert sorted(d.code for d in out.deductions) == [
        "atr_pct_rank", "degraded", "event_risk", "ripster_stack_conflict", "weekly_disagrees",
    ]  # fmt: skip
    assert sum(d.points for d in out.deductions) == 55.0


def test_confidence_clipped_to_zero(cfg: ScoringConfig) -> None:
    """TS-CMP-027: agreement 0.30 (supertrend, volume_osc, volatility positive) minus 55 clips to 0.

    Composite (30*100 - 70*1)/100 = 29.3 > 0, so agreement is 30/100.
    """
    positive = ("supertrend", "volume_osc", "volatility")
    scores = {fid: (100.0 if fid in positive else -1.0) for fid in FACTOR_IDS}
    out = _all_penalties(cfg, make_results(scores))
    assert out.agreement == pytest.approx(0.30, abs=1e-12)
    assert out.value == 0.0


def test_confidence_zero_composite_sign_handling(cfg: ScoringConfig) -> None:
    """TS-CMP-028: a composite of 0 agrees with factors scoring exactly 0 (sign 0 equals sign 0).

    All zero: agreement 1.0. Supertrend +10 (200) against ripster -20 (-200): composite 0, the
    remaining 70 points score 0, so agreement 0.70.
    """
    assert _conf(cfg, make_results(default=0.0)).agreement == pytest.approx(1.0, abs=1e-12)
    mixed = make_results({"supertrend": 10.0, "ripster": -20.0})
    out = _conf(cfg, mixed)
    assert out.agreement == pytest.approx(0.70, abs=1e-12)
    assert out.value == pytest.approx(70.0, abs=1e-9)


def test_confidence_missing_excluded_from_agreement(cfg: ScoringConfig) -> None:
    """TS-CMP-029: a missing factor (score 0) is out of numerator and denominator.

    Everything else positive: agreement is 1.0, not 92/100, whatever weight is passed for it.
    """
    results = make_results(default=30.0, missing=("fundamentals",))
    base_weights = dict(zip(FACTOR_IDS, (20, 7, 8, 9, 7, 5, 7, 4, 6, 9, 8, 10), strict=True))
    out = compute_confidence(
        make_snapshot(), results, {k: float(v) for k, v in base_weights.items()}, 30.0, cfg
    )
    assert out.agreement == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize(
    ("scenario", "st_d", "stack", "points"),
    [
        ("TS-CMP-031", 1.0, -1.0, 10.0),
        ("TS-CMP-031", -1.0, 1.0, 10.0),
        ("TS-CMP-032", 1.0, 1.0, 0.0),
        ("TS-CMP-032", 1.0, 0.0, 0.0),
        ("TS-CMP-032", -1.0, -1.0, 0.0),
        ("TS-CMP-032", -1.0, 0.0, 0.0),
        ("TS-CMP-113", 0.0, 0.0, 0.0),  # no direction yet, no stack: -0 == 0 must not fire
        ("TS-CMP-113", 1.0, None, 0.0),  # stack not available
    ],
)
def test_confidence_ripster_stack_conflict(
    cfg: ScoringConfig, scenario: str, st_d: float, stack: float | None, points: float
) -> None:
    """TS-CMP-031, 032, 113: rc_stack == -st_dir_d (non-zero) subtracts the configured 10; else nothing."""  # noqa: E501
    snap = make_snapshot(st_dir_d=st_d, st_dir_w=st_d, rc_stack=stack)
    out = _conf(cfg, make_results(default=30.0), snap)
    assert out.value == pytest.approx(100.0 - points, abs=1e-9)
    fired = [d for d in out.deductions if d.code == "ripster_stack_conflict"]
    assert len(fired) == (1 if points else 0)
    if fired:
        assert fired[0].points == points
        assert "Ripster" in fired[0].reason


def test_confidence_ripster_penalty_comes_from_config(cfg: ScoringConfig) -> None:
    """TS-CMP-114: the deduction is ripster.confidence_stack_conflict_penalty (7 here), not a constant."""  # noqa: E501
    moved = cfg.model_copy(
        update={
            "ripster": cfg.ripster.model_copy(update={"confidence_stack_conflict_penalty": 7.0})
        }
    )
    snap = make_snapshot(st_dir_d=1.0, st_dir_w=1.0, rc_stack=-1.0)
    assert _conf(moved, make_results(default=30.0), snap).value == pytest.approx(93.0, abs=1e-9)


def test_confidence_ripster_worked_example(cfg: ScoringConfig) -> None:
    """TS-CMP-033: agreement 0.80, st_dir_d -1, rc_stack +1 (weekly -1): 80 - 10 = 70."""
    snap = make_snapshot(st_dir_d=-1.0, st_dir_w=-1.0, rc_stack=1.0)
    out = _conf(cfg, _split_results(("supertrend",)), snap)
    assert out.agreement == pytest.approx(0.80, abs=1e-12)
    assert out.value == pytest.approx(70.0, abs=1e-9)


def test_confidence_fr327_worked_example_atr_and_weekly(cfg: ScoringConfig) -> None:
    """TS-CMP-115: FR-327: agreement 0.80, atr rank 95, weekly disagreement: 80 - 15 - 10 = 55."""
    snap = make_snapshot(atr_pct_rank=95.0, st_dir_d=1.0, st_dir_w=-1.0, rc_stack=1.0)
    out = _conf(cfg, _split_results(("supertrend",)), snap)
    assert out.value == pytest.approx(55.0, abs=1e-9)


def test_confidence_missing_snapshot_path_names_it(cfg: ScoringConfig) -> None:
    """TS-CMP-116: a snapshot without a confidence input path is a KeyError naming the path."""
    snap = make_snapshot()
    del snap["ripster"]
    with pytest.raises(KeyError, match=r"ripster\.stack"):
        _conf(cfg, make_results(default=30.0), snap)


# ---- ScoreCard -------------------------------------------------------------------------------


def test_score_ticker_worked_example(cfg: ScoringConfig) -> None:
    """TS-CMP-101: end to end on the hand example.

    composite 3000/92 = 32.6087; display (32.6087+100)/2 = 66.3043 -> 66.3; band Buy. Positive
    weight: supertrend 20, sma 7, macd 8, mean_reversion 7, volatility 4, volume_osc 6, ripster 10
    = 62 of 92, so confidence 100*62/92 = 67.3913 with no deductions (benign snapshot).
    """
    results = make_results(EXAMPLE_SCORES, missing=("fundamentals",))
    card = score_ticker(make_snapshot(), results, make_context(cfg))
    assert card.composite == pytest.approx(3000 / 92, abs=1e-12)
    assert card.display_score == 66.3
    assert card.band is Band.BUY
    assert card.agreement == pytest.approx(62 / 92, abs=1e-12)
    assert card.confidence == pytest.approx(6200 / 92, abs=1e-9)
    assert card.deductions == ()
    assert abs(sum(card.contributions.values()) - card.composite) < 1e-9
    assert sum(card.weights.values()) == pytest.approx(100.0, abs=1e-9)
    assert card.scores["supertrend"] == 80.0
    assert card.qualities["fundamentals"] is Quality.MISSING
    assert card.regime == "transitional"  # adx 22
    assert card.regime_applied is None
    assert card.event_risk is False
    assert card.adjustments == card.weight_detail.adjustments


def test_score_card_is_frozen_and_read_only(cfg: ScoringConfig) -> None:
    """TS-CMP-102: the card is a frozen record with read-only mappings."""
    card = score_ticker(make_snapshot(), make_results(default=10.0), make_context(cfg))
    with pytest.raises(dataclasses.FrozenInstanceError):
        card.composite = 0.0  # type: ignore[misc]
    with pytest.raises(TypeError):
        card.contributions["sma"] = 1.0  # type: ignore[index]
    with pytest.raises(TypeError):
        card.weights["sma"] = 1.0  # type: ignore[index]


def test_score_ticker_injected_regime_applies_multipliers(cfg: ScoringConfig) -> None:
    """TS-CMP-103: context.regime drives the multipliers; the ADX regime is reported either way.

    Without an injected regime (Sprint 3) ADX 30 is labelled trending but weights stay base. With
    "trending" injected the weights are the FR-318 example: supertrend 25/104.1*100 = 24.0154.
    """
    snap = make_snapshot(adx=30.0)
    results = make_results(default=10.0)
    plain = score_ticker(snap, results, make_context(cfg))
    assert plain.regime == "trending"
    assert plain.regime_applied is None
    assert plain.weights["supertrend"] == pytest.approx(20.0, abs=1e-12)
    tilted = score_ticker(snap, results, make_context(cfg, regime="trending"))
    assert tilted.regime_applied == "trending"
    assert tilted.weights["supertrend"] == pytest.approx(2500 / 104.1, abs=1e-12)
    assert "trending regime" in tilted.adjustments


def test_score_ticker_earnings_sets_event_risk_and_deduction(cfg: ScoringConfig) -> None:
    """TS-CMP-104: earnings in 3 days: event_risk, 'earnings in 3 days' adjustment, confidence minus 10."""  # noqa: E501
    results = make_results(default=30.0)
    card = score_ticker(make_snapshot(), results, make_context(cfg, days_to_earnings=3))
    assert card.event_risk is True
    assert "earnings in 3 days" in card.adjustments
    assert [d.code for d in card.deductions] == ["event_risk"]
    assert card.confidence == pytest.approx(90.0, abs=1e-9)
    flagged = score_ticker(make_snapshot(), results, make_context(cfg, event_risk=True))
    assert flagged.event_risk is True
    assert flagged.confidence == pytest.approx(90.0, abs=1e-9)


def test_score_ticker_all_missing_raises(cfg: ScoringConfig) -> None:
    """TS-CMP-105: nothing to score raises NoScorableFactorsError."""
    with pytest.raises(NoScorableFactorsError):
        score_ticker(make_snapshot(), make_results(missing=FACTOR_IDS), make_context(cfg))


def test_score_ticker_missing_adx_is_transitional(cfg: ScoringConfig) -> None:
    """TS-CMP-106: ADX still in warm-up (null) labels the regime transitional."""
    card = score_ticker(make_snapshot(adx=None), make_results(default=10.0), make_context(cfg))
    assert card.regime == "transitional"


def test_score_ticker_is_deterministic_and_pure(cfg: ScoringConfig) -> None:
    """TS-CMP-107: same inputs give equal cards; inputs are not mutated."""
    snap = make_snapshot()
    results = make_results(EXAMPLE_SCORES, missing=("fundamentals",))
    snap_before = repr(snap)
    results_before = dict(results)
    first = score_ticker(snap, results, make_context(cfg))
    second = score_ticker(snap, results, make_context(cfg))
    assert first == second
    assert repr(snap) == snap_before
    assert results == results_before


def test_score_ticker_degraded_is_listed_with_reason(cfg: ScoringConfig) -> None:
    """TS-CMP-108: deductions carry a human reason, in the order atr, degraded, weekly, ripster, event."""  # noqa: E501
    results = make_results(default=30.0, qualities={"fundamentals": Quality.DEGRADED})
    snap = make_snapshot(atr_pct_rank=95.0, st_dir_d=1.0, st_dir_w=-1.0, rc_stack=-1.0)
    card = score_ticker(snap, results, make_context(cfg, days_to_earnings=2))
    assert [d.code for d in card.deductions] == [
        "atr_pct_rank", "degraded", "weekly_disagrees", "ripster_stack_conflict", "event_risk",
    ]  # fmt: skip
    assert all(d.reason for d in card.deductions)
    assert "95.00" in card.deductions[0].reason


@settings(max_examples=200, deadline=None)
@given(
    scores=st.lists(
        st.floats(min_value=-100, max_value=100, allow_nan=False), min_size=12, max_size=12
    ),
    missing=st.sets(st.integers(min_value=0, max_value=11), max_size=11),
    degraded=st.booleans(),
    regime=st.sampled_from([None, "trending", "ranging", "transitional"]),
    atr=st.one_of(st.none(), st.floats(min_value=0, max_value=100)),
    st_d=st.sampled_from([-1.0, 0.0, 1.0]),
    st_w=st.sampled_from([None, -1.0, 1.0]),
    stack=st.sampled_from([None, -1.0, 0.0, 1.0]),
    days=st.one_of(st.none(), st.integers(min_value=0, max_value=20)),
)
def test_all_outputs_in_range_for_random_scores(  # noqa: PLR0917
    scores: list[float],
    missing: set[int],
    degraded: bool,
    regime: str | None,
    atr: float | None,
    st_d: float,
    st_w: float | None,
    stack: float | None,
    days: int | None,
) -> None:
    """TS-CMP-030 and TS-CMP-002: composite -100..100, display 0..100, confidence 0..100, contributions sum to composite."""  # noqa: E501
    cfg = load_cfg()
    results = make_results(
        dict(zip(FACTOR_IDS, scores, strict=True)),
        missing=tuple(FACTOR_IDS[i] for i in missing),
        qualities={"flow": Quality.DEGRADED} if degraded else None,
    )
    card = score_ticker(
        make_snapshot(atr_pct_rank=atr, st_dir_d=st_d, st_dir_w=st_w, rc_stack=stack),
        results,
        make_context(cfg, regime=regime, days_to_earnings=days),
    )
    assert -100.0 <= card.composite <= 100.0
    assert 0.0 <= card.display_score <= 100.0
    assert 0.0 <= card.confidence <= 100.0
    assert 0.0 <= card.agreement <= 1.0
    assert abs(sum(card.contributions.values()) - card.composite) < 1e-9
