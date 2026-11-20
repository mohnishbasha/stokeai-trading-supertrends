# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
# ruff: noqa: PLR0917
"""Factor 6, Fibonacci retracement (S3-T03; BUILD_PROMPT Factor 6; PRD FR-308, FR-309; 10.4.6).

Hand-made legs, atr14 = 2 so `near` is within 1.0 of a level (config `near_atr` 0.5).

Up leg A=100 (low), B=200 (high). Levels measured from B back toward A, `B - (B-A) * ratio`:
23.6% 176.4, 38.2% 161.8, 50% 150.0, 61.8% 138.2, 78.6% 121.4. Extensions `A + (B-A) * ratio`:
127.2% 227.2, 161.8% 261.8.

Down leg A=200 (high), B=100 (low). Levels `B + (A-B) * ratio`:
23.6% 123.6, 38.2% 138.2, 50% 150.0, 61.8% 161.8, 78.6% 178.6. Extensions `A - (A-B) * ratio`:
127.2% 72.8, 161.8% 38.2.
"""

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from supertrends.scoring.config import ScoringConfig, load_scoring_config
from supertrends.scoring.factor import FactorContext, Quality
from supertrends.scoring.factors.fibonacci import FACTOR
from supertrends.scoring.snapshot import compute_snapshot
from tests.unit.indicators.lookahead_support import make_bundle

CONFIG = Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"

RATIOS = (0.236, 0.382, 0.5, 0.618, 0.786)
EXT_RATIOS = (1.272, 1.618)
UP_LEVELS = (176.4, 161.8, 150.0, 138.2, 121.4)
DOWN_LEVELS = (123.6, 138.2, 150.0, 161.8, 178.6)
UP_EXT = (227.2, 261.8)
DOWN_EXT = (72.8, 38.2)


@pytest.fixture(scope="module")
def cfg() -> ScoringConfig:
    return load_scoring_config(CONFIG)


@pytest.fixture(scope="module")
def ctx(cfg: ScoringConfig) -> FactorContext:
    return FactorContext(config=cfg, as_of=date(2026, 1, 2))


def snap(
    close: float,
    prev: float,
    low: float,
    high: float,
    *,
    d: int = 1,
    atr: float | None = 2.0,
) -> dict[str, Any]:
    levels, ext = (UP_LEVELS, UP_EXT) if d > 0 else (DOWN_LEVELS, DOWN_EXT)
    a, b = (100.0, 200.0) if d > 0 else (200.0, 100.0)
    return {
        "fib": {
            "leg": {"a_index": 10, "a_price": a, "b_index": 60, "b_price": b, "direction": d},
            "retracements": [{"ratio": r, "price": p} for r, p in zip(RATIOS, levels, strict=True)],
            "extensions": [{"ratio": r, "price": p} for r, p in zip(EXT_RATIOS, ext, strict=True)],
        },
        "daily": {"close": close, "prev_close": prev, "low": low, "high": high, "atr": atr},
    }


# (close, prev_close, low, high, expected) for an up leg.
UP_ROWS = [
    pytest.param(
        162.0, 161.0, 161.0, 163.0, 60.0, id="38.2: |162-161.8|=0.2, up close, low 161>=160.8"
    ),
    pytest.param(
        150.5, 150.0, 149.5, 151.0, 70.0, id="50: |150.5-150|=0.5, up close, low 149.5>=149"
    ),
    pytest.param(138.5, 138.0, 138.0, 139.0, 80.0, id="61.8: |138.5-138.2|=0.3, low 138>=137.2"),
    pytest.param(121.0, 122.0, 120.0, 123.0, -50.0, id="close 121 < 78.6 level 121.4: failed"),
    pytest.param(201.0, 199.0, 198.0, 202.0, 20.0, id="close 201 > B 200: resumed"),
    pytest.param(170.0, 169.0, 168.0, 171.0, 0.0, id="170: near none, inside the leg: 0"),
]


@pytest.mark.parametrize(("close", "prev", "low", "high", "expected"), [UP_ROWS[0]])
def test_unit_fib_score_up_leg_near_38_2_and_holding_adds_60(
    ctx: FactorContext, close: float, prev: float, low: float, high: float, expected: float
) -> None:
    """TS-SCR-100: up leg near the 38.2 level and holding -> +60."""
    assert FACTOR.compute(snap(close, prev, low, high), ctx).score == expected


@pytest.mark.parametrize(("close", "prev", "low", "high", "expected"), [UP_ROWS[1]])
def test_unit_fib_score_up_leg_near_50_and_holding_adds_70(
    ctx: FactorContext, close: float, prev: float, low: float, high: float, expected: float
) -> None:
    """TS-SCR-101: up leg near the 50 level and holding -> +70."""
    assert FACTOR.compute(snap(close, prev, low, high), ctx).score == expected


@pytest.mark.parametrize(("close", "prev", "low", "high", "expected"), [UP_ROWS[2]])
def test_unit_fib_score_up_leg_near_61_8_and_holding_adds_80(
    ctx: FactorContext, close: float, prev: float, low: float, high: float, expected: float
) -> None:
    """TS-SCR-102: up leg near the 61.8 level and holding -> +80."""
    assert FACTOR.compute(snap(close, prev, low, high), ctx).score == expected


@pytest.mark.parametrize(
    ("close", "prev", "low", "high", "expected"),
    [
        UP_ROWS[3],
        pytest.param(
            121.4, 122.0, 120.0, 123.0, 0.0, id="close equal to the 78.6 level is not below"
        ),
        pytest.param(121.39, 122.0, 120.0, 123.0, -50.0, id="just below the 78.6 level"),
    ],
)
def test_unit_fib_score_up_leg_close_below_78_6_subtracts_50(
    ctx: FactorContext, close: float, prev: float, low: float, high: float, expected: float
) -> None:
    """TS-SCR-103: up leg, close below the 78.6 level (strict) -> -50, the swing has failed."""
    assert FACTOR.compute(snap(close, prev, low, high), ctx).score == expected


@pytest.mark.parametrize(
    ("close", "prev", "low", "high", "expected"),
    [
        UP_ROWS[4],
        pytest.param(200.0, 199.0, 198.0, 201.0, 0.0, id="close equal to B is not above"),
        pytest.param(200.01, 199.0, 198.0, 201.0, 20.0, id="just above B"),
    ],
)
def test_unit_fib_score_up_leg_close_above_b_adds_20(
    ctx: FactorContext, close: float, prev: float, low: float, high: float, expected: float
) -> None:
    """TS-SCR-104: up leg, close above B (strict) -> +20, the leg resumed."""
    assert FACTOR.compute(snap(close, prev, low, high), ctx).score == expected


@pytest.mark.parametrize(
    ("close", "prev", "low", "high", "expected"),
    [
        UP_ROWS[5],
        pytest.param(130.0, 129.0, 128.0, 131.0, 0.0, id="between 61.8 and 78.6, not near either"),
        pytest.param(185.0, 184.0, 183.0, 186.0, 0.0, id="above the 23.6 level, below B"),
    ],
)
def test_unit_fib_score_up_leg_otherwise_zero(
    ctx: FactorContext, close: float, prev: float, low: float, high: float, expected: float
) -> None:
    """TS-SCR-105: no rule matches -> 0 with quality ok."""
    res = FACTOR.compute(snap(close, prev, low, high), ctx)
    assert res.score == expected
    assert res.quality is Quality.OK


@pytest.mark.parametrize(
    ("d", "close", "prev", "low", "high", "expected"),
    [
        # up: level 150, band 0.5 * 2 = 1.0; |151.0 - 150.0| = 1.0 is near (<=), holding ok
        pytest.param(1, 151.0, 150.5, 150.0, 151.5, 70.0, id="up exactly 1.0 above the level"),
        pytest.param(1, 149.0, 148.5, 149.0, 150.0, 70.0, id="up exactly 1.0 below the level"),
        pytest.param(1, 151.01, 150.5, 150.0, 151.5, 0.0, id="up just beyond the band"),
        # down: mirror, holding needs close < prev and high <= 151.0
        pytest.param(-1, 149.0, 149.5, 148.0, 150.0, -70.0, id="down exactly 1.0 below the level"),
        pytest.param(-1, 151.0, 151.5, 150.0, 151.0, -70.0, id="down exactly 1.0 above the level"),
        pytest.param(-1, 148.99, 149.5, 148.0, 150.0, 0.0, id="down just beyond the band"),
    ],
)
def test_unit_fib_score_near_boundary_exactly_half_atr_counts_as_near(
    ctx: FactorContext, d: int, close: float, prev: float, low: float, high: float, expected: float
) -> None:
    """TS-SCR-106: `abs(close - level) <= 0.5*atr14` counts as near (inclusive)."""
    assert FACTOR.compute(snap(close, prev, low, high, d=d), ctx).score == expected


@pytest.mark.parametrize(
    ("d", "close", "prev", "low", "high", "expected"),
    [
        # up, level 150 (band 1.0): holding needs close > prev and low >= 149.0
        pytest.param(1, 150.5, 150.0, 149.0, 151.0, 70.0, id="up: low exactly level-1.0 holds"),
        pytest.param(1, 150.5, 150.0, 148.99, 151.0, 0.0, id="up: low below level-1.0 fails"),
        pytest.param(1, 150.5, 150.5, 149.5, 151.0, 0.0, id="up: close equal prior close fails"),
        pytest.param(1, 150.5, 151.0, 149.5, 151.0, 0.0, id="up: close below prior close fails"),
        # down mirror: close < prev and high <= 151.0
        pytest.param(
            -1, 149.5, 150.0, 148.0, 151.0, -70.0, id="down: high exactly level+1.0 holds"
        ),
        pytest.param(-1, 149.5, 150.0, 148.0, 151.01, 0.0, id="down: high above level+1.0 fails"),
        pytest.param(-1, 149.5, 149.5, 148.0, 150.5, 0.0, id="down: close equal prior close fails"),
        pytest.param(-1, 149.5, 149.0, 148.0, 150.5, 0.0, id="down: close above prior close fails"),
    ],
)
def test_unit_fib_score_holding_requires_close_above_prior_close_and_low_ge_level_minus_half_atr(
    ctx: FactorContext, d: int, close: float, prev: float, low: float, high: float, expected: float
) -> None:
    """TS-SCR-107: both `holding` conditions are required (mirrored for a down leg)."""
    assert FACTOR.compute(snap(close, prev, low, high, d=d), ctx).score == expected


DOWN_CASES = {
    "38.2": (138.0, 139.0, 137.0, 139.0, -60.0),  # |138-138.2|=0.2; close<prev; high 139<=139.2
    "50": (149.5, 150.0, 148.5, 150.5, -70.0),  # |149.5-150|=0.5; high 150.5<=151
    "61.8": (161.5, 162.0, 160.5, 162.0, -80.0),  # |161.5-161.8|=0.3; high 162<=162.8
}


@pytest.mark.parametrize(("close", "prev", "low", "high", "expected"), [DOWN_CASES["38.2"]])
def test_unit_fib_score_down_leg_near_38_2_and_holding_subtracts_60(
    ctx: FactorContext, close: float, prev: float, low: float, high: float, expected: float
) -> None:
    """TS-SCR-108: down leg near 38.2 and holding -> -60 (mirror of +60)."""
    assert FACTOR.compute(snap(close, prev, low, high, d=-1), ctx).score == expected


@pytest.mark.parametrize(("close", "prev", "low", "high", "expected"), [DOWN_CASES["50"]])
def test_unit_fib_score_down_leg_near_50_and_holding_subtracts_70(
    ctx: FactorContext, close: float, prev: float, low: float, high: float, expected: float
) -> None:
    """TS-SCR-109: down leg near 50 and holding -> -70 (mirror)."""
    assert FACTOR.compute(snap(close, prev, low, high, d=-1), ctx).score == expected


@pytest.mark.parametrize(("close", "prev", "low", "high", "expected"), [DOWN_CASES["61.8"]])
def test_unit_fib_score_down_leg_near_61_8_and_holding_subtracts_80(
    ctx: FactorContext, close: float, prev: float, low: float, high: float, expected: float
) -> None:
    """TS-SCR-110: down leg near 61.8 and holding -> -80 (mirror)."""
    assert FACTOR.compute(snap(close, prev, low, high, d=-1), ctx).score == expected


@pytest.mark.parametrize(
    ("close", "prev", "low", "high", "expected"),
    [
        pytest.param(179.0, 178.0, 177.0, 180.0, 50.0, id="close 179 > 78.6 level 178.6"),
        pytest.param(178.6, 178.0, 177.0, 180.0, 0.0, id="close equal to the level is not above"),
        pytest.param(178.61, 178.0, 177.0, 180.0, 50.0, id="just above the level"),
    ],
)
def test_unit_fib_score_down_leg_close_above_78_6_adds_50(
    ctx: FactorContext, close: float, prev: float, low: float, high: float, expected: float
) -> None:
    """TS-SCR-111: down leg, close above the 78.6 level -> +50 (mirror of the failure rule)."""
    assert FACTOR.compute(snap(close, prev, low, high, d=-1), ctx).score == expected


@pytest.mark.parametrize(
    ("close", "prev", "low", "high", "expected"),
    [
        pytest.param(99.0, 101.0, 98.0, 102.0, -20.0, id="close 99 < B 100"),
        pytest.param(100.0, 101.0, 98.0, 102.0, 0.0, id="close equal to B is not below"),
        pytest.param(99.99, 101.0, 98.0, 102.0, -20.0, id="just below B"),
    ],
)
def test_unit_fib_score_down_leg_close_below_b_subtracts_20(
    ctx: FactorContext, close: float, prev: float, low: float, high: float, expected: float
) -> None:
    """TS-SCR-112: down leg, close below B -> -20 (mirror: the leg resumed)."""
    assert FACTOR.compute(snap(close, prev, low, high, d=-1), ctx).score == expected


def test_unit_fib_score_no_leg_score_zero_quality_degraded(ctx: FactorContext) -> None:
    """TS-SCR-113: no qualifying leg -> 0, degraded."""
    doc = snap(150.0, 149.0, 148.0, 151.0)
    doc["fib"] = {"leg": None, "retracements": [], "extensions": []}
    res = FACTOR.compute(doc, ctx)
    assert (res.score, res.quality) == (0.0, Quality.DEGRADED)
    assert res.evidence[0].name == "fib_leg"
    assert res.evidence[0].reason == "No completed swing leg qualifies, so Fibonacci is neutral"


@pytest.mark.parametrize(
    ("d", "level", "far", "a", "b", "direction"),
    [
        (1, 227.2, 261.8, "100.00", "200.00", "up"),
        (-1, 72.8, 38.2, "200.00", "100.00", "down"),
    ],
)
def test_unit_fib_score_evidence_includes_next_level_127_2_extension(
    ctx: FactorContext, d: int, level: float, far: float, a: str, b: str, direction: str
) -> None:
    """TS-SCR-114: the next target (127.2 extension) is evidence, with the 161.8 beyond it."""
    res = FACTOR.compute(snap(170.0, 169.0, 168.0, 171.0, d=d), ctx)
    by_name = {e.name: e for e in res.evidence}
    assert by_name["fib_next_level_127_2"].value == level
    assert by_name["fib_next_level_127_2"].unit == "price"
    assert by_name["fib_next_level_127_2"].reason == (
        f"Next level is the 127.2 percent extension at {level:.2f}"
    )
    assert by_name["fib_level_161_8"].value == far
    assert by_name["fib_leg"].reason == (
        f"Last swing leg runs {direction} from {a} to {b}; levels are measured back from {b}"
    )


def test_unit_fib_first_listed_rule_wins_when_two_levels_are_near(ctx: FactorContext) -> None:
    """TS-SCR-364: rules are tried in listed order (PRD A-28); each needs its own `holding`."""
    # atr 20 -> band 10.  close 156: |156-161.8|=5.8 and |156-150|=6 are both near.
    # 38.2 rule: low must be >= 161.8-10 = 151.8.  50 rule: low must be >= 150-10 = 140.
    both = snap(156.0, 155.0, 155.0, 157.0, atr=20.0)
    assert FACTOR.compute(both, ctx).score == 60.0  # 38.2 listed first
    only_fifty = snap(156.0, 155.0, 148.0, 157.0, atr=20.0)  # low 148 < 151.8 fails 38.2 holding
    assert FACTOR.compute(only_fifty, ctx).score == 70.0
    # down mirror, levels 138.2 and 150: close 144 near both (5.8, 6), band 10.
    # 38.2 rule: high <= 138.2+10 = 148.2.  50 rule: high <= 160.
    d_both = snap(144.0, 145.0, 143.0, 145.0, d=-1, atr=20.0)
    assert FACTOR.compute(d_both, ctx).score == -60.0
    d_fifty = snap(144.0, 145.0, 143.0, 152.0, d=-1, atr=20.0)  # high 152 > 148.2
    assert FACTOR.compute(d_fifty, ctx).score == -70.0


def test_unit_fib_missing_price_inputs_make_the_factor_missing(ctx: FactorContext) -> None:
    """TS-SCR-365: null close, prior close, low, high or ATR -> missing, score 0."""
    for key in ("close", "prev_close", "low", "high", "atr"):
        doc = snap(150.0, 149.0, 148.0, 151.0)
        doc["daily"][key] = None
        res = FACTOR.compute(doc, ctx)
        assert (res.score, res.quality) == (0.0, Quality.MISSING), key


def test_unit_fib_fail_rule_is_ignored_while_a_hold_rule_matches(ctx: FactorContext) -> None:
    """TS-SCR-366: hold rules come before the failure and resume rules (listed order)."""
    # atr 100 -> band 50.  Up leg close 95 < 121.4 (failed), but |95-138.2|=43.2 is near 61.8
    # while |95-161.8|=66.8 and |95-150|=55 are not near the earlier levels.  Holding for 61.8:
    # close 95 > prev 90 and low 92 >= 138.2-50 = 88.2.  The hold rule comes first: +80, not -50.
    doc = snap(95.0, 90.0, 92.0, 96.0, atr=100.0)
    assert FACTOR.compute(doc, ctx).score == 80.0
    # down mirror: close 205 > 178.6 (failed up for the mirror), |205-161.8|=43.2 near 61.8,
    # |205-138.2|=66.8 and |205-150|=55 are not near; holding: close 205 < prev 210 and
    # high 208 <= 161.8+50 = 211.8.  -80, not +50.
    mirror = snap(205.0, 210.0, 204.0, 208.0, d=-1, atr=100.0)
    assert FACTOR.compute(mirror, ctx).score == -80.0


def test_unit_fib_on_real_snapshots_scores_in_range(ctx: FactorContext, cfg: ScoringConfig) -> None:
    """TS-SCR-367: computed snapshots give an in-range score; no leg means degraded."""
    seen = set()
    for seed in range(12):
        bundle = make_bundle(seed=seed, n=400, intraday_from=None)
        doc = compute_snapshot(bundle, cfg, date.fromisoformat(str(bundle.dates[-1])))
        res = FACTOR.compute(doc, ctx)
        assert -100.0 <= res.score <= 100.0
        has_leg = doc["fib"]["leg"] is not None
        assert (res.quality is Quality.OK) is has_leg
        seen.add(has_leg)
    assert True in seen


def test_unit_fib_absent_extensions_leave_out_the_target_evidence(ctx: FactorContext) -> None:
    """TS-SCR-368: with no extensions in the snapshot the score is unchanged, targets omitted."""
    doc = snap(170.0, 169.0, 168.0, 171.0)
    doc["fib"]["extensions"] = []
    res = FACTOR.compute(doc, ctx)
    assert res.score == 0.0
    assert not {"fib_next_level_127_2", "fib_level_161_8"} & {e.name for e in res.evidence}
