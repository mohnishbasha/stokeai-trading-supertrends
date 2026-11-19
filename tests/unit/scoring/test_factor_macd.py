# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 3, MACD: every rule line, both signs, boundaries (S3-T02; TS-SCR-050 to 062)."""

from __future__ import annotations

from typing import Any

import pytest

from supertrends.scoring.factor import Quality
from supertrends.scoring.factors.macd import FACTOR
from tests.unit.scoring.factor_support import context, evidence_by_name, load_cfg

CFG = load_cfg()
CTX = context(CFG)
UP_W = (1.0, 0.5)  # weekly line above signal
DOWN_W = (-1.0, -0.5)  # weekly line below signal
BARS = 300  # bars in the snapshot; a cross at index i is (BARS - i) bars back counting the last bar


def snap(
    line: float = 0.0,
    signal: float = 0.0,
    run: int = 0,
    cross: tuple[int, int] | None = None,
    weekly: tuple[float, float] | None = UP_W,
) -> dict[str, Any]:
    """The Factor 3 slice. Defaults tie line, signal and zero; no run, no cross.

    `cross` is (bars back counting the as-of bar as 1, direction). `weekly` is (line, signal), by
    default above its signal; None leaves the weekly values null.
    """
    w_line, w_signal = (None, None) if weekly is None else weekly
    return {
        "bars": BARS,
        "daily": {
            "macd": {"line": line, "signal": signal, "hist": line - signal},
            "macd_hist_run": run,
            "macd_cross": None
            if cross is None
            else {"index": BARS - cross[0], "direction": cross[1]},
        },
        "weekly": {"macd": {"line": w_line, "signal": w_signal}},
    }


# Hand sums: +-35 line vs signal, +-25 line vs zero, +-25 histogram run, +-15 cross within the
# last 3 bars; then x0.75 when the weekly line-vs-signal sign differs from the daily one.
RULE_ROWS = [
    # TS-SCR-050: line 0.5 above signal 0.3 (+35), above zero (+25)
    pytest.param(snap(0.5, 0.3, weekly=UP_W), 60.0, id="TS-SCR-050-line-above-signal"),
    # TS-SCR-051: line -0.5 below signal -0.2 (-35), below zero (-25)
    pytest.param(snap(-0.5, -0.2, weekly=DOWN_W), -60.0, id="TS-SCR-051-line-below-signal"),
    # TS-SCR-052: line above zero but below signal: -35 + 25
    pytest.param(
        snap(0.2, 0.5, weekly=DOWN_W), -10.0, id="TS-SCR-052-line-above-zero-below-signal"
    ),
    # TS-SCR-053: line below zero but above signal: +35 - 25
    pytest.param(snap(-0.2, -0.5, weekly=UP_W), 10.0, id="TS-SCR-053-line-below-zero-above-signal"),
    # line equal to signal adds neither 35 sign; above zero +25
    pytest.param(snap(0.3, 0.3, weekly=UP_W), 25.0, id="TS-SCR-050-line-equals-signal"),
    # line exactly zero adds neither 25 sign; above signal +35
    pytest.param(snap(0.0, -0.3, weekly=UP_W), 35.0, id="TS-SCR-052-line-equals-zero"),
    # TS-SCR-054: histogram rising for 3 bars (run +1) adds 25 to the all-tied base of 0
    pytest.param(snap(run=1), 25.0, id="TS-SCR-054-hist-rising-3-bars"),
    # TS-SCR-055: a run of 2 bars is run 0 in the snapshot (S2 hist_run needs 3): adds 0
    pytest.param(snap(run=0), 0.0, id="TS-SCR-055-hist-rising-2-bars"),
    # TS-SCR-056: falling for 3 bars (run -1)
    pytest.param(snap(run=-1), -25.0, id="TS-SCR-056-hist-falling-3-bars"),
    # TS-SCR-057: bullish cross 3 bars back (the as-of bar is bar 1) counts: +15
    pytest.param(snap(cross=(3, 1)), 15.0, id="TS-SCR-057-bullish-cross-3-bars-ago"),
    pytest.param(snap(cross=(1, 1)), 15.0, id="TS-SCR-057-bullish-cross-on-the-last-bar"),
    # TS-SCR-058: 4 bars back does not
    pytest.param(snap(cross=(4, 1)), 0.0, id="TS-SCR-058-bullish-cross-4-bars-ago"),
    # TS-SCR-059: bearish cross within 3 bars: -15, and the 3 / 4 boundary
    pytest.param(snap(cross=(2, -1)), -15.0, id="TS-SCR-059-bearish-cross-2-bars-ago"),
    pytest.param(snap(cross=(3, -1)), -15.0, id="TS-SCR-059-bearish-cross-3-bars-ago"),
    pytest.param(snap(cross=(4, -1)), 0.0, id="TS-SCR-059-bearish-cross-4-bars-ago"),
    # all bullish: 35 + 25 + 25 + 15 = 100 (at the cap), weekly agrees
    pytest.param(snap(0.5, 0.3, 1, (2, 1), UP_W), 100.0, id="max-bullish"),
    # all bearish: -35 - 25 - 25 - 15 = -100
    pytest.param(snap(-0.5, -0.3, -1, (2, -1), DOWN_W), -100.0, id="max-bearish"),
    # TS-SCR-060: daily +60 (line above signal and zero), weekly line below signal: 60 * 0.75
    pytest.param(snap(0.5, 0.3, weekly=DOWN_W), 45.0, id="TS-SCR-060-weekly-disagrees-bullish"),
    # TS-SCR-060: daily -60, weekly line above signal: -60 * 0.75
    pytest.param(snap(-0.5, -0.2, weekly=UP_W), -45.0, id="TS-SCR-060-weekly-disagrees-bearish"),
    # the multiplier follows the capped sum: 100 * 0.75
    pytest.param(snap(0.5, 0.3, 1, (2, 1), DOWN_W), 75.0, id="TS-SCR-060-disagree-on-the-cap"),
    # TS-SCR-061: weekly agrees: 60, unchanged
    pytest.param(snap(0.5, 0.3, weekly=UP_W), 60.0, id="TS-SCR-061-weekly-agrees"),
    # a weekly tie (line equals signal) is not a disagreement: 60
    pytest.param(snap(0.5, 0.3, weekly=(0.4, 0.4)), 60.0, id="TS-SCR-061-weekly-tie"),
    # a daily tie has no direction to disagree with: 25 (line above zero), no multiplier
    pytest.param(snap(0.3, 0.3, weekly=DOWN_W), 25.0, id="TS-SCR-061-daily-tie"),
]


@pytest.mark.parametrize(("snapshot", "expected"), RULE_ROWS)
def test_unit_macd_score_rule_lines(snapshot: dict[str, Any], expected: float) -> None:
    """TS-SCR-050 to 061: the score for each rule line, both signs, ties and boundaries."""
    res = FACTOR.compute(snapshot, CTX)
    assert res.factor_id == "macd"
    assert res.quality is Quality.OK
    assert res.score == pytest.approx(expected)


def test_unit_macd_weekly_multiplier_and_cross_window_follow_the_config() -> None:
    """TS-SCR-326: the 0.75 and the 3-bar window come from the config."""
    macd = CFG.macd.model_copy(update={"weekly_disagree_multiplier": 0.5, "cross_lookback": 2})
    ctx = context(CFG.model_copy(update={"macd": macd}))
    assert FACTOR.compute(snap(0.5, 0.3, weekly=DOWN_W), ctx).score == 30.0  # 60 * 0.5
    assert FACTOR.compute(snap(cross=(2, 1)), ctx).score == 15.0
    assert FACTOR.compute(snap(cross=(3, 1)), ctx).score == 0.0


def test_unit_macd_score_weekly_macd_reported_as_evidence() -> None:
    """TS-SCR-062: the weekly line and signal are in the evidence, with the daily ones."""
    res = FACTOR.compute(snap(0.5, 0.3, 1, (2, 1), DOWN_W), CTX)
    assert evidence_by_name(res) == {
        "macd_line": (0.5, "price", "MACD line 0.50 is above the signal 0.30"),
        "macd_line_vs_zero": (0.5, "price", "MACD line 0.50 is above zero"),
        "macd_hist_run": (1, "bars", "MACD histogram rose for 3 consecutive bars"),
        "macd_cross": (1, "cross", "Bullish MACD signal cross 2 bars ago"),
        "weekly_macd_line": (
            -1.0,
            "price",
            "Weekly MACD line -1.00 is below the weekly signal -0.50",
        ),
        "weekly_macd_signal": (-0.5, "price", "Weekly MACD signal is -0.50"),
        "weekly_macd_multiplier": (
            0.75,
            "multiplier",
            "Weekly MACD disagrees with daily, so the score is multiplied by 0.75",
        ),
    }


def test_unit_macd_evidence_wording_for_bearish_and_agreeing_weekly() -> None:
    """TS-SCR-062: below, falling, bearish cross, and agreeing weekly wording."""
    res = FACTOR.compute(snap(-0.5, -0.2, -1, (3, -1), DOWN_W), CTX)
    ev = evidence_by_name(res)
    assert ev["macd_line"][2] == "MACD line -0.50 is below the signal -0.20"
    assert ev["macd_line_vs_zero"][2] == "MACD line -0.50 is below zero"
    assert ev["macd_hist_run"][2] == "MACD histogram fell for 3 consecutive bars"
    assert ev["macd_cross"][2] == "Bearish MACD signal cross 3 bars ago"
    assert ev["weekly_macd_line"][2] == "Weekly MACD line -1.00 is below the weekly signal -0.50"
    assert ev["weekly_macd_multiplier"] == (
        1.0,
        "multiplier",
        "Weekly MACD agrees with daily, so the score is unchanged",
    )
    quiet = evidence_by_name(FACTOR.compute(snap(0.3, 0.3, weekly=(0.4, 0.4)), CTX))
    assert quiet["macd_line"][2] == "MACD line 0.30 is equal to the signal 0.30"
    assert quiet["macd_line_vs_zero"][2] == "MACD line 0.30 is above zero"
    assert quiet["macd_hist_run"][2] == "MACD histogram has no 3-bar run"
    assert quiet["macd_cross"] == (0, "cross", "No MACD signal cross in the last 3 bars")
    assert (
        quiet["weekly_macd_line"][2] == "Weekly MACD line 0.40 is equal to the weekly signal 0.40"
    )
    assert quiet["weekly_macd_multiplier"][2] == (
        "Weekly or daily MACD is level with its signal, so the score is unchanged"
    )


def test_unit_macd_weekly_unavailable_is_degraded_without_the_multiplier() -> None:
    """TS-SCR-325: no weekly MACD leaves the score unscaled and flags the factor degraded."""
    res = FACTOR.compute(snap(0.5, 0.3, weekly=None), CTX)
    assert res.quality is Quality.DEGRADED
    assert res.score == pytest.approx(60.0)
    ev = evidence_by_name(res)
    assert ev["weekly_macd_line"] == (None, "price", "Weekly MACD is not available")


@pytest.mark.parametrize("path", [("macd", "line"), ("macd", "signal")])
def test_unit_macd_warmup_returns_missing(path: tuple[str, str]) -> None:
    """TS-SCR-325: a null daily line or signal (warm-up) is missing with score 0."""
    snapshot = snap(0.5, 0.3, weekly=UP_W)
    snapshot["daily"][path[0]][path[1]] = None
    res = FACTOR.compute(snapshot, CTX)
    assert res.quality is Quality.MISSING
    assert res.score == 0
    assert res.reasons == ("MACD is not available (not enough history)",)
    assert FACTOR.compute({}, CTX).quality is Quality.MISSING
