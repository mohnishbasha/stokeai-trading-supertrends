# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 12, Ripster EMA Clouds: score rules (BUILD_PROMPT Factor 12, FR-333; S3-T14).

Expected values are worked by hand from the rule lines with points 30/20/20/10/10/10. The base
snapshot has c2 and c3 bullish and everything else 0, so trend = +20 and mid = +10 (score 30);
each row changes one rule line.
"""

from datetime import date
from typing import Any

import numpy as np
import pytest

from supertrends.indicators.registry import Bundle
from supertrends.indicators.ripster_clouds import EmaCloud, ripster_pullback
from supertrends.scoring.factor import FactorContext, FactorResult, Quality, get_path
from supertrends.scoring.factors import default_registry
from supertrends.scoring.factors.ripster import FACTOR, INPUT_PATHS
from supertrends.scoring.snapshot import compute_snapshot
from tests.unit.indicators.lookahead_support import make_bundle
from tests.unit.scoring.ripster_support import config_with, default_config, snapshot

AS_OF = date(2026, 11, 13)


def _score(snap: dict[str, Any], **ripster: Any) -> FactorResult:
    cfg = config_with(**ripster) if ripster else default_config()
    return FACTOR.compute(snap, FactorContext(config=cfg, as_of=AS_OF))


def _component(res: FactorResult, name: str) -> float:
    (item,) = [e for e in res.evidence if e.name == name]
    assert isinstance(item.value, int | float)
    return float(item.value)


# (scenario, snapshot kwargs, component name, expected component points, expected score)
RULE_ROWS = [
    ("TS-SCR-180", {"bias": 1.0}, "bias", 30, 60),  # 30 + 20 + 10
    ("TS-SCR-181", {"bias": -1.0}, "bias", -30, 0),  # -30 + 20 + 10
    ("TS-SCR-182", {"bias": 0.0}, "bias", 0, 30),  # pos(c3) = 0 scores 0: 0 + 20 + 10
    ("TS-SCR-183", {"c2_dir": 1.0}, "trend", 20, 30),  # 0 + 20 + 10
    ("TS-SCR-184", {"c2_dir": -1.0}, "trend", -20, -10),  # -20 + 10
    ("TS-SCR-185", {"stack": 1.0}, "stacking", 20, 50),  # 20 + 20 + 10
    ("TS-SCR-186", {"stack": -1.0}, "stacking", -20, 10),  # -20 + 20 + 10
    ("TS-SCR-187", {"stack": 0.0}, "stacking", 0, 30),  # overlap: 0 + 20 + 10
    ("TS-SCR-188", {"c3_dir": 1.0}, "mid", 10, 30),  # 20 + 10
    ("TS-SCR-189", {"c3_dir": -1.0}, "mid", -10, 10),  # 20 - 10
    ("TS-SCR-190", {"c5_pos": 1.0}, "long", 10, 40),  # 20 + 10 + 10
    ("TS-SCR-191", {"c5_pos": -1.0}, "long", -10, 20),  # 20 + 10 - 10
    ("TS-SCR-192", {"c5_pos": 0.0}, "long", 0, 30),  # inside c5: 20 + 10
    # Held bullish pullback: stack +1 gives stacking 20, pullback flag 1 gives +10: 20+10+20+10.
    ("TS-SCR-193", {"stack": 1.0, "pullback": 1.0}, "pullback", 10, 60),
    # Failed or stale: the snapshot flag is 0, so no pullback points: 20 + 10 + 20.
    ("TS-SCR-194", {"stack": 1.0, "pullback": 0.0}, "pullback", 0, 50),
    # Held bearish: c2 and c3 down (-20, -10), stack -1 (-20), pullback flag -1 (-10).
    (
        "TS-SCR-197",
        {"stack": -1.0, "pullback": -1.0, "c2_dir": -1.0, "c3_dir": -1.0},
        "pullback",
        -10,
        -60,
    ),
    (
        "TS-SCR-198",
        {"stack": -1.0, "pullback": 0.0, "c2_dir": -1.0, "c3_dir": -1.0},
        "pullback",
        0,
        -50,
    ),
    # Pullback requires stack != 0, even when the flag says tested: 20 + 10 only.
    ("TS-SCR-199", {"stack": 0.0, "pullback": 1.0}, "pullback", 0, 30),
]


@pytest.mark.parametrize(
    ("scenario", "kwargs", "component", "points", "score"),
    RULE_ROWS,
    ids=[r[0] + "-" + r[2] for r in RULE_ROWS],
)
def test_unit_ripster_score_rule_line(
    scenario: str, kwargs: dict[str, Any], component: str, points: float, score: float
) -> None:
    """TS-SCR-180 to TS-SCR-199: one rule line per row, both signs."""
    res = _score(snapshot(**kwargs))
    assert _component(res, component) == points, scenario
    assert res.score == score, scenario
    assert res.factor_id == "ripster"
    assert res.quality is Quality.OK


def test_unit_ripster_score_all_components_bullish_maximum_30_20_20_10_10_10_is_100() -> None:
    """TS-SCR-200: 30 + 20 + 20 + 10 + 10 + 10 = 100."""
    res = _score(snapshot(bias=1.0, c2_dir=1.0, stack=1.0, c3_dir=1.0, c5_pos=1.0, pullback=1.0))
    assert res.score == 100


def test_unit_ripster_score_all_components_bearish_maximum_is_minus_100() -> None:
    """TS-SCR-201: -30 - 20 - 20 - 10 - 10 - 10 = -100."""
    res = _score(
        snapshot(bias=-1.0, c2_dir=-1.0, stack=-1.0, c3_dir=-1.0, c5_pos=-1.0, pullback=-1.0)
    )
    assert res.score == -100


def test_unit_ripster_score_clip_to_plus_minus_100_when_points_exceed() -> None:
    """TS-SCR-420: points 60 for bias lift the sum to 130 (60+20+20+10+10+10), clipped to 100."""
    snap = snapshot(bias=1.0, c2_dir=1.0, stack=1.0, c3_dir=1.0, c5_pos=1.0, pullback=1.0)
    points = {"bias": 60, "trend": 20, "stack": 20, "mid": 10, "long": 10, "pullback": 10}
    assert _score(snap, points=points).score == 100
    bear = snapshot(bias=-1.0, c2_dir=-1.0, stack=-1.0, c3_dir=-1.0, c5_pos=-1.0, pullback=-1.0)
    assert _score(bear, points=points).score == -100


def test_unit_ripster_score_c4_72_89_cloud_is_evidence_only_not_scored() -> None:
    """TS-SCR-202: changing the 72/89 cloud leaves the score and the components unchanged."""
    from tests.unit.scoring.ripster_support import cloud  # noqa: PLC0415

    base = _score(snapshot(bias=1.0, stack=1.0))
    flipped = _score(snapshot(bias=1.0, stack=1.0, c4=cloud(10.0, 5.0, -1.0, -1.0)))
    assert flipped.score == base.score == 80  # 30 + 20 + 20 + 10
    assert [e.value for e in flipped.evidence] == [e.value for e in base.evidence]


def test_unit_ripster_score_points_read_from_config_ripster_key() -> None:
    """TS-SCR-421: halving every points value halves the score (60 -> 30)."""
    snap = snapshot(bias=1.0)  # 30 + 20 + 10 = 60 at the shipped points
    half = {"bias": 15, "trend": 10, "stack": 10, "mid": 5, "long": 5, "pullback": 5}
    assert _score(snap).score == 60
    assert _score(snap, points=half).score == 30


def test_unit_ripster_score_evidence_lists_six_components_and_derived_rc_values() -> None:
    """TS-SCR-204: six components and the derived rc_* values, each with a unit and a reason."""
    res = _score(snapshot(bias=1.0, stack=1.0, pullback=1.0, bars_since_stack_flip=12.0, dir_w=1.0))
    names = [e.name for e in res.evidence]
    assert names == [
        "bias",
        "trend",
        "stacking",
        "mid",
        "long",
        "pullback",
        "rc_bias",
        "rc_stack",
        "rc_bars_since_stack_flip",
        "rc_c3_top",
        "rc_c3_bot",
        "rc_dir_w",
    ]
    by_name = {e.name: e for e in res.evidence}
    assert by_name["rc_bias"].value == 1
    assert by_name["rc_stack"].value == 1
    assert by_name["rc_bars_since_stack_flip"].value == 12
    assert by_name["rc_c3_top"].value == 210.8
    assert by_name["rc_c3_bot"].value == 206.3
    assert by_name["rc_dir_w"].value == 1
    assert all(e.unit and e.reason for e in res.evidence)
    # Components sum to the (unclipped) score: 30 + 20 + 20 + 10 + 0 + 10 = 90.
    assert sum(_component(res, n) for n in names[:6]) == res.score == 90


def test_unit_ripster_score_reasons_are_deterministic_and_name_the_rule() -> None:
    """TS-SCR-422: reasons come from templates: same input, same text; each names its rule."""
    snap = snapshot(bias=-1.0, stack=1.0, pullback=1.0, bars_since_stack_flip=3.0)
    a, b = _score(snap), _score(snap)
    assert a.reasons == b.reasons
    by_name = {e.name: e.reason for e in a.evidence}
    assert by_name["bias"] == "Close is below the 34/50 cloud, subtracting 30 points"
    assert by_name["stacking"] == "The 5/12 cloud is fully above the 34/50 cloud, adding 20 points"
    assert by_name["pullback"] == "Held pullback into the 8/9 cloud, adding 10 points"
    assert by_name["rc_bars_since_stack_flip"] == "The cloud stack last flipped 3 bars ago"


@pytest.mark.parametrize(
    "missing_path",
    ["bias", "stack", "c2_dir", "c3_dir"],
)
def test_unit_ripster_score_missing_core_input_is_missing_quality_score_zero(
    missing_path: str,
) -> None:
    """TS-SCR-423: warm-up nulls in a core input make the factor missing (score 0, excluded)."""
    res = _score(snapshot(**{missing_path: None}))
    assert res.is_missing
    assert res.score == 0
    assert res.reasons == ("Ripster EMA Clouds are not available: fewer than 50 bars of history",)


def test_unit_ripster_score_c5_not_defined_yet_scores_long_zero_and_is_degraded() -> None:
    """TS-SCR-424: with 50 to 199 bars the 180/200 cloud is null: long = 0, quality degraded."""
    res = _score(snapshot(bias=1.0, c5_pos=None))
    assert _component(res, "long") == 0
    assert res.score == 60  # 30 + 20 + 10 + 0
    assert res.quality is Quality.DEGRADED
    assert "180/200" in next(e.reason for e in res.evidence if e.name == "long")


def test_unit_ripster_score_is_pure_and_does_not_mutate_the_snapshot() -> None:
    """TS-SCR-425: same snapshot in, same result out, snapshot untouched."""
    import copy  # noqa: PLC0415

    snap = snapshot(bias=1.0, stack=-1.0, pullback=-1.0)
    before = copy.deepcopy(snap)
    assert _score(snap) == _score(snap)
    assert snap == before


# --- the pullback rule end to end: bars -> ripster_pullback -> snapshot flag -> score ----------


def _flat_c1(n: int, top: float = 100.0, bot: float = 98.0) -> EmaCloud:
    nan = np.full(n, np.nan)
    return EmaCloud(nan, nan, np.full(n, top), np.full(n, bot), nan, nan)


def _pullback_score(
    stack_value: float,
    low: list[float],
    high: list[float],
    close: list[float],
    lookback: int = 3,
) -> float:
    """Pullback component from hand-built bars: c1 is the constant cloud 98..100."""
    n = len(close)
    flag = ripster_pullback(
        np.array(high),
        np.array(low),
        np.array(close),
        _flat_c1(n),
        np.full(n, stack_value),
        lookback=lookback,
    )[-1]
    kwargs: dict[str, Any] = {"stack": stack_value, "pullback": float(flag)}
    if stack_value < 0:
        kwargs.update(c2_dir=-1.0, c3_dir=-1.0)
    res = _score(snapshot(**kwargs), pullback_lookback_bars=lookback)
    return _component(res, "pullback")


UP = [110.0] * 5  # lows well above the cloud top (100): no test
HIGH_UP = [115.0] * 5


def test_unit_ripster_score_pullback_held_stack_plus_1_low_2_bars_ago_close_above_bot_c1_adds_10() -> (
    None
):  # noqa: E501
    """TS-SCR-193 (end to end): bar t-2 low 99.5 <= top(c1) 100, close 105 > bot(c1) 98: +10."""
    low = [110.0, 110.0, 99.5, 110.0, 110.0]
    assert _pullback_score(1.0, low, HIGH_UP, [112.0, 112.0, 105.0, 112.0, 105.0]) == 10


def test_unit_ripster_score_pullback_failed_close_at_or_below_bot_c1_is_0() -> None:
    """TS-SCR-194 (end to end): test at t, but close 98 is not above bot(c1) 98: 0; 97 also 0."""
    low = [110.0, 110.0, 110.0, 110.0, 97.0]
    assert _pullback_score(1.0, low, HIGH_UP, [112.0] * 4 + [98.0]) == 0
    assert _pullback_score(1.0, low, HIGH_UP, [112.0] * 4 + [97.0]) == 0
    assert _pullback_score(1.0, low, HIGH_UP, [112.0] * 4 + [98.01]) == 10  # boundary above


def test_unit_ripster_score_pullback_stale_test_4_bars_ago_is_0() -> None:
    """TS-SCR-195 (end to end): the only test is at t-4 (index 0 of 5 bars): outside t-2..t."""
    low = [99.0, 110.0, 110.0, 110.0, 110.0]
    assert _pullback_score(1.0, low, HIGH_UP, [105.0] * 5) == 0


def test_unit_ripster_score_pullback_test_3_bars_ago_counts() -> None:
    """TS-SCR-196: resolved with PRD A-25. The window is t-2..t, so the oldest bar in the window
    (t-2, the third bar counting t) counts; a test at t-3 is outside it."""
    in_window = [110.0, 110.0, 99.0, 110.0, 110.0]  # test at t-2
    outside = [110.0, 99.0, 110.0, 110.0, 110.0]  # test at t-3
    assert _pullback_score(1.0, in_window, HIGH_UP, [105.0] * 5) == 10
    assert _pullback_score(1.0, outside, HIGH_UP, [105.0] * 5) == 0


def test_unit_ripster_score_pullback_bearish_end_to_end_held_failed_and_stale() -> None:
    """TS-SCR-426: bearish: high >= bot(c1) 98 within t-2..t and close < top(c1) 100."""
    low = [90.0] * 5
    held = [90.0, 90.0, 98.0, 90.0, 90.0]  # high 98 >= 98 two bars ago
    assert _pullback_score(-1.0, low, held, [95.0] * 5) == -10
    assert _pullback_score(-1.0, low, held, [95.0] * 4 + [100.0]) == 0  # close not below top
    stale = [98.0, 90.0, 90.0, 90.0, 90.0]
    assert _pullback_score(-1.0, low, stale, [95.0] * 5) == 0


def test_unit_ripster_score_pullback_lookback_read_from_config_ripster_key() -> None:
    """TS-SCR-203: ripster.pullback_lookback_bars = 5 admits a test at t-4; 3 does not."""
    low = [99.0, 110.0, 110.0, 110.0, 110.0]  # test at t-4
    assert _pullback_score(1.0, low, HIGH_UP, [105.0] * 5, lookback=3) == 0
    assert _pullback_score(1.0, low, HIGH_UP, [105.0] * 5, lookback=5) == 10


# --- the factor on a computed snapshot ------------------------------------------------------


@pytest.fixture(scope="module")
def bundle() -> Bundle:
    return make_bundle(seed=7, n=420, intraday_from=400)


def test_unit_ripster_score_on_computed_snapshot_reads_every_declared_input(
    bundle: Bundle,
) -> None:
    """TS-SCR-427: the factor runs on `compute_snapshot` output, stays in range and agrees with
    an independent evaluation of the rule lines from the same snapshot fields."""
    cfg = default_config()
    doc = compute_snapshot(bundle, cfg, date.fromisoformat(str(bundle.dates[-1])))
    for path in INPUT_PATHS:
        assert get_path(doc, path) is not None or path.endswith("bars_since_stack_flip")
    res = FACTOR.compute(doc, FactorContext(config=cfg, as_of=AS_OF))
    r = doc["ripster"]
    stack = r["stack"]
    pull = 10 * stack if (stack != 0 and r["pullback"] != 0) else 0
    expected = (
        30 * r["bias"]
        + 20 * r["c2_dir"]
        + 20 * stack
        + 10 * r["c3_dir"]
        + 10 * r["clouds"]["c5"]["pos"]
        + pull
    )
    assert res.score == max(-100.0, min(100.0, expected))
    assert -100 <= res.score <= 100
    assert res.quality is Quality.OK


def test_unit_ripster_score_registry_factor_is_the_module_factor() -> None:
    """TS-SCR-428: the registry's `ripster` computes (no longer the S3-T14 stub)."""
    f = default_registry().get("ripster")
    assert f is FACTOR
    res = f.compute(snapshot(bias=1.0), FactorContext(config=default_config(), as_of=AS_OF))
    assert res.score == 60
