# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 1, Supertrend: every rule line, both signs, boundaries (S3-T02; TS-SCR-010 to 024)."""

from __future__ import annotations

from typing import Any

import pytest

from supertrends.scoring.factor import Quality
from supertrends.scoring.factors.supertrend import FACTOR, INPUT_PATHS
from tests.unit.scoring.factor_support import context, evidence_by_name, load_cfg

CFG = load_cfg()
CTX = context(CFG)


def snap(  # noqa: PLR0917
    d: float | None = 1.0,
    w: float | None = 1.0,
    bars_since_flip: float | None = 20.0,
    distance: float | None = 1.0,
    line: float | None = 100.0,
    atr: float | None = 2.0,
) -> dict[str, Any]:
    """The snapshot slice Factor 1 reads. Defaults: up, weekly agrees, old flip, near the line."""
    return {
        "daily": {
            "supertrend": {"direction": d, "line": line},
            "bars_since_flip": bars_since_flip,
            "distance_atr": distance,
            "atr": atr,
        },
        "weekly": {"supertrend_direction": w},
    }


# (case id, snapshot, expected score). Every expected value is the hand sum of the rule lines:
# base +-60; weekly +25*d agrees or -15*d conflicts; freshness +15*d if bars_since_flip <= 5;
# stretch -10*d if |distance| > 4. Defaults are old flip (no freshness) and distance 1 (no stretch).
RULE_ROWS = [
    # TS-SCR-010 base +60 (weekly conflicts, so base is visible apart from the weekly 25): 60 - 15
    pytest.param(snap(d=1, w=-1), 45.0, id="TS-SCR-010-up-base-60-with-conflict"),
    # TS-SCR-011 base -60: -60 + 15 (conflict, -15 * -1)
    pytest.param(snap(d=-1, w=1), -45.0, id="TS-SCR-011-down-base-60-with-conflict"),
    # TS-SCR-012 weekly agrees, up: 60 + 25
    pytest.param(snap(d=1, w=1), 85.0, id="TS-SCR-012-weekly-agrees-up"),
    # TS-SCR-013 weekly agrees, down: -60 + 25 * -1 = -85
    pytest.param(snap(d=-1, w=-1), -85.0, id="TS-SCR-013-weekly-agrees-down"),
    # TS-SCR-014 weekly conflicts, daily up: 60 - 15 * 1 = 45
    pytest.param(snap(d=1, w=-1), 45.0, id="TS-SCR-014-weekly-conflict-up"),
    # TS-SCR-015 weekly conflicts, daily down: -60 - 15 * -1 = -45
    pytest.param(snap(d=-1, w=1), -45.0, id="TS-SCR-015-weekly-conflict-down"),
    # TS-SCR-016 flip 5 bars ago counts: 60 - 15 + 15
    pytest.param(snap(d=1, w=-1, bars_since_flip=5.0), 60.0, id="TS-SCR-016-flip-5-adds-15"),
    # TS-SCR-017 flip 6 bars ago does not: 60 - 15 + 0
    pytest.param(snap(d=1, w=-1, bars_since_flip=6.0), 45.0, id="TS-SCR-017-flip-6-adds-0"),
    # the flip bar itself (0 bars ago) is the freshest: 60 - 15 + 15
    pytest.param(snap(d=1, w=-1, bars_since_flip=0.0), 60.0, id="TS-SCR-016-flip-0-adds-15"),
    # TS-SCR-018 fresh flip down: -60 + 15 (conflict) + 15 * -1
    pytest.param(snap(d=-1, w=1, bars_since_flip=2.0), -60.0, id="TS-SCR-018-fresh-down-15"),
    pytest.param(snap(d=-1, w=1, bars_since_flip=5.0), -60.0, id="TS-SCR-018-fresh-down-5"),
    pytest.param(snap(d=-1, w=1, bars_since_flip=6.0), -45.0, id="TS-SCR-018-down-6-no-fresh"),
    # TS-SCR-019 |distance| == 4 is not over 4: 60 + 25, no stretch (either side of the line)
    pytest.param(snap(distance=4.0), 85.0, id="TS-SCR-019-distance-4-up"),
    pytest.param(snap(d=-1, w=-1, distance=-4.0), -85.0, id="TS-SCR-019-distance-minus-4-down"),
    # TS-SCR-020 4.01 up: 60 + 25 - 10
    pytest.param(snap(distance=4.01), 75.0, id="TS-SCR-020-distance-4.01-up"),
    # TS-SCR-021 4.01 down: -60 - 25 + 10
    pytest.param(snap(d=-1, w=-1, distance=-4.01), -75.0, id="TS-SCR-021-distance-4.01-down"),
    # the stretch test uses the absolute distance, so the wrong side of the line counts too
    pytest.param(snap(distance=-4.01), 75.0, id="TS-SCR-020-distance-abs-wrong-side"),
    # TS-SCR-022 max up: 60 + 25 + 15 = 100 (already at the cap)
    pytest.param(snap(bars_since_flip=1.0), 100.0, id="TS-SCR-022-max-up"),
    # TS-SCR-023 max down: -60 - 25 - 15 = -100
    pytest.param(snap(d=-1, w=-1, bars_since_flip=1.0), -100.0, id="TS-SCR-023-max-down"),
    # fresh and stretched together: 60 + 25 + 15 - 10
    pytest.param(snap(bars_since_flip=3.0, distance=5.0), 90.0, id="up-fresh-and-stretched"),
    pytest.param(
        snap(d=-1, w=-1, bars_since_flip=3.0, distance=-5.0), -90.0, id="down-fresh-and-stretched"
    ),
]


@pytest.mark.parametrize(("snapshot", "expected"), RULE_ROWS)
def test_unit_supertrend_score_rule_lines(snapshot: dict[str, Any], expected: float) -> None:
    """TS-SCR-010 to 023: the score for each rule line, both signs and boundaries."""
    res = FACTOR.compute(snapshot, CTX)
    assert res.factor_id == "supertrend"
    assert res.quality is Quality.OK
    assert res.score == pytest.approx(expected)


def test_unit_supertrend_score_reads_thresholds_from_the_config() -> None:
    """TS-SCR-326: the freshness and stretch limits come from the config, not constants."""
    tight = CFG.model_copy(
        update={
            "supertrend": CFG.supertrend.model_copy(
                update={"fresh_flip_bars": 2, "stretch_atr": 1.0}
            )
        }
    )
    ctx = context(tight)
    # 60 + 25 + 15 (bars 2 <= 2) - 10 (|1.5| > 1)
    assert FACTOR.compute(snap(bars_since_flip=2.0, distance=1.5), ctx).score == 90.0
    # 60 + 25 (bars 3 > 2) + 0 (|1.0| is not over 1)
    assert FACTOR.compute(snap(bars_since_flip=3.0, distance=1.0), ctx).score == 85.0


def test_unit_supertrend_score_evidence_includes_line_direction_bars_since_flip_distance() -> None:
    """TS-SCR-024: evidence has direction, weekly direction, line, ATR, flip age, distance."""
    res = FACTOR.compute(snap(bars_since_flip=3.0, distance=1.5, line=100.0, atr=2.0), CTX)
    assert evidence_by_name(res) == {
        "st_dir_d": (1, "direction", "Daily Supertrend is up"),
        "st_dir_w": (
            1,
            "direction",
            "Weekly Supertrend is up, which agrees with the daily trend",
        ),
        "st_line": (100.0, "price", "Supertrend line (invalidation level) is 100.00"),
        "st_atr": (2.0, "price", "Supertrend ATR(10) is 2.00"),
        "bars_since_flip": (3, "bars", "Supertrend flipped 3 bars ago, a fresh flip"),
        "st_distance_atr": (1.5, "atr", "Close is 1.50 ATR from the Supertrend line"),
    }


def test_unit_supertrend_evidence_reasons_for_down_conflict_old_stretched() -> None:
    """TS-SCR-024: the down, conflicting, old-flip, stretched wording."""
    res = FACTOR.compute(snap(d=-1, w=1, bars_since_flip=12.0, distance=-4.5, line=50.0), CTX)
    ev = evidence_by_name(res)
    assert ev["st_dir_d"][2] == "Daily Supertrend is down"
    assert ev["st_dir_w"][2] == "Weekly Supertrend is up, which conflicts with the daily trend"
    assert ev["bars_since_flip"][2] == "Supertrend flipped 12 bars ago"
    assert ev["st_distance_atr"][2] == (
        "Close is -4.50 ATR from the Supertrend line, stretched beyond 4.00 ATR (late entry)"
    )
    # -60 + 15 + 0 (12 bars) + 10 (|-4.5| > 4)
    assert res.score == pytest.approx(-35.0)


def test_unit_supertrend_weekly_unavailable_is_degraded_and_scores_the_rest() -> None:
    """TS-SCR-325: no weekly direction contributes 0 and flags the factor degraded."""
    res = FACTOR.compute(snap(d=1, w=None, bars_since_flip=1.0), CTX)
    assert res.quality is Quality.DEGRADED
    assert res.score == pytest.approx(75.0)  # 60 + 0 + 15
    assert evidence_by_name(res)["st_dir_w"] == (
        None,
        "direction",
        "Weekly Supertrend is not available",
    )


def test_unit_supertrend_distance_unavailable_is_degraded_with_no_stretch() -> None:
    """TS-SCR-325: a null distance (zero ATR) is degraded, with no stretch penalty."""
    res = FACTOR.compute(snap(distance=None), CTX)
    assert res.quality is Quality.DEGRADED
    assert res.score == pytest.approx(85.0)
    ev = evidence_by_name(res)
    assert ev["st_distance_atr"] == (
        None,
        "atr",
        "Distance from the Supertrend line is not available",
    )


def test_unit_supertrend_atr_unavailable_is_degraded() -> None:
    """TS-SCR-325: a null ATR is degraded, the other rule lines still score."""
    res = FACTOR.compute(snap(atr=None), CTX)
    assert res.quality is Quality.DEGRADED
    assert res.score == pytest.approx(85.0)  # 60 + 25, old flip, near the line
    assert evidence_by_name(res)["st_atr"] == (None, "price", "Supertrend ATR is not available")


@pytest.mark.parametrize(
    "snapshot",
    [
        snap(d=None),
        snap(line=None),
        snap(bars_since_flip=None),
        {},
        {"daily": {}, "weekly": {}},
    ],
    ids=["no-direction", "no-line", "no-flip-age", "empty", "empty-blocks"],
)
def test_unit_supertrend_missing_inputs_return_missing_with_score_zero(
    snapshot: dict[str, Any],
) -> None:
    """TS-SCR-325: warm-up (null direction, line or flip age) or absent keys are missing."""
    res = FACTOR.compute(snapshot, CTX)
    assert res.quality is Quality.MISSING
    assert res.score == 0
    assert res.reasons == ("Supertrend is not available (not enough history)",)


def test_unit_supertrend_declares_its_input_paths() -> None:
    """TS-SCR-024: the factor reads exactly the declared paths (a missing one makes it missing)."""
    assert FACTOR.input_paths == INPUT_PATHS
