# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 2, SMA stack and slope: every rule line, both signs (S3-T02; TS-SCR-030 to 043)."""

from __future__ import annotations

from typing import Any

import pytest

from supertrends.scoring.factor import Quality
from supertrends.scoring.factors.sma import FACTOR
from tests.unit.scoring.factor_support import context, evidence_by_name, load_cfg

CFG = load_cfg()
CTX = context(CFG)
BARS = 300  # bars in the snapshot; a cross at index i is (BARS - i) bars back counting the last bar


def snap(  # noqa: PLR0917
    close: float = 100.0,
    sma50: float = 100.0,
    sma200: float = 100.0,
    slope20: float | None = 0.0,
    cross: tuple[int, int] | None = None,
    sma20: float = 100.0,
) -> dict[str, Any]:
    """The Factor 2 slice. Defaults tie everything (close = SMA50 = SMA200), flat slope, no cross.

    `cross` is (bars back counting the as-of bar as 1, direction).
    """
    return {
        "bars": BARS,
        "daily": {
            "close": close,
            "sma_20": sma20,
            "sma_50": sma50,
            "sma_200": sma200,
            "sma_slope_20": slope20,
            "sma_cross": None
            if cross is None
            else {"index": BARS - cross[0], "direction": cross[1]},
        },
    }


# Expected scores are hand sums: +-30 close vs SMA200, +-25 SMA50 vs SMA200, +-20 close vs SMA50,
# +-15 SMA20 slope sign, +-10 cross within the last 10 bars; a tie adds neither sign.
RULE_ROWS = [
    # TS-SCR-030/034: close 105 above SMA200 100 (+30), SMA50 = SMA200 (0), close above SMA50 (+20)
    pytest.param(snap(105, 100, 100), 50.0, id="TS-SCR-030-close-above-sma200"),
    # TS-SCR-031/035: mirror, -30 + 0 - 20
    pytest.param(snap(95, 100, 100), -50.0, id="TS-SCR-031-close-below-sma200"),
    # TS-SCR-032: SMA50 110 above SMA200 100 (+25); close 105 is above SMA200 (+30) and below
    # SMA50 (-20): 30 + 25 - 20
    pytest.param(snap(105, 110, 100), 35.0, id="TS-SCR-032-sma50-above-sma200"),
    # TS-SCR-033: mirror; close 95 below SMA200 (-30), SMA50 90 below SMA200 (-25), close above
    # SMA50 (+20)
    pytest.param(snap(95, 90, 100), -35.0, id="TS-SCR-033-sma50-below-sma200"),
    # SMA50 above SMA200 with close tied to SMA50: 30 + 25 + 0
    pytest.param(snap(100, 100, 90), 55.0, id="TS-SCR-032-sma50-above-close-tied"),
    pytest.param(snap(100, 100, 110), -55.0, id="TS-SCR-033-sma50-below-close-tied"),
    # TS-SCR-034: close above SMA50 while below SMA200 (bear market rally): -30 - 25 + 20 = -35
    pytest.param(snap(103, 100, 110), -35.0, id="TS-SCR-034-close-above-sma50"),
    # TS-SCR-035: close below SMA50 while above SMA200 (pullback): 30 + 25 - 20 = 35
    pytest.param(snap(103, 105, 100), 35.0, id="TS-SCR-035-close-below-sma50"),
    # TS-SCR-036: slope positive adds 15 to the all-tied base of 0
    pytest.param(snap(slope20=0.01), 15.0, id="TS-SCR-036-slope-positive"),
    # TS-SCR-037: slope negative
    pytest.param(snap(slope20=-0.01), -15.0, id="TS-SCR-037-slope-negative"),
    # a flat slope (exactly 0) adds neither sign
    pytest.param(snap(slope20=0.0), 0.0, id="TS-SCR-036-slope-zero"),
    # TS-SCR-038: golden cross exactly 10 bars back counts (the as-of bar is bar 1 of the 10)
    pytest.param(snap(cross=(10, 1)), 10.0, id="TS-SCR-038-golden-10-bars-ago"),
    pytest.param(snap(cross=(1, 1)), 10.0, id="TS-SCR-038-golden-on-the-last-bar"),
    # TS-SCR-039: 11 bars back does not
    pytest.param(snap(cross=(11, 1)), 0.0, id="TS-SCR-039-golden-11-bars-ago"),
    # TS-SCR-040: death cross within 10 bars, and the same boundaries
    pytest.param(snap(cross=(4, -1)), -10.0, id="TS-SCR-040-death-4-bars-ago"),
    pytest.param(snap(cross=(10, -1)), -10.0, id="TS-SCR-040-death-10-bars-ago"),
    pytest.param(snap(cross=(11, -1)), 0.0, id="TS-SCR-040-death-11-bars-ago"),
    # TS-SCR-041: 30 + 25 + 20 + 15 + 10 = 100 (at the cap)
    pytest.param(snap(120, 110, 100, 0.5, (3, 1)), 100.0, id="TS-SCR-041-all-bullish"),
    # TS-SCR-042: -30 - 25 - 20 - 15 - 10 = -100
    pytest.param(snap(80, 90, 100, -0.5, (3, -1)), -100.0, id="TS-SCR-042-all-bearish"),
    # TS-SCR-043: close equal to SMA200 and SMA50: neither sign (0 + 0 + 0)
    pytest.param(snap(100, 100, 100), 0.0, id="TS-SCR-043-ties-add-nothing"),
    # close equal to SMA50 only, both above SMA200 (110 vs 100): 30 + 25 + 0
    pytest.param(snap(110, 110, 100), 55.0, id="TS-SCR-043-close-equals-sma50"),
    # SMA50 equals SMA200, close above both: 30 + 0 + 20
    pytest.param(snap(110, 100, 100), 50.0, id="TS-SCR-043-sma50-equals-sma200"),
]


@pytest.mark.parametrize(("snapshot", "expected"), RULE_ROWS)
def test_unit_sma_score_rule_lines(snapshot: dict[str, Any], expected: float) -> None:
    """TS-SCR-030 to 043: the score for each rule line, both signs, ties and boundaries."""
    res = FACTOR.compute(snapshot, CTX)
    assert res.factor_id == "sma"
    assert res.quality is Quality.OK
    assert res.score == pytest.approx(expected)


def test_unit_sma_cross_window_follows_the_config_lookback() -> None:
    """TS-SCR-326: the cross window is sma.cross_lookback, not a literal 10."""
    short = CFG.model_copy(update={"sma": CFG.sma.model_copy(update={"cross_lookback": 4})})
    ctx = context(short)
    assert FACTOR.compute(snap(cross=(4, 1)), ctx).score == 10.0
    assert FACTOR.compute(snap(cross=(5, 1)), ctx).score == 0.0


def test_unit_sma_evidence_lists_averages_slope_and_cross_with_reasons() -> None:
    """TS-SCR-041: evidence for the three averages, the slope, and the cross."""
    res = FACTOR.compute(snap(120, 110, 100, 0.5, (3, 1), sma20=115), CTX)
    assert evidence_by_name(res) == {
        "close_vs_sma_200": (100.0, "price", "Close 120.00 is above the 200-day average 100.00"),
        "sma_50_vs_sma_200": (
            110.0,
            "price",
            "The 50-day average 110.00 is above the 200-day average 100.00",
        ),
        "close_vs_sma_50": (110.0, "price", "Close 120.00 is above the 50-day average 110.00"),
        "sma_20_slope": (
            0.5,
            "price",
            "The 20-day average 115.00 rose 0.50 over 5 bars",
        ),
        "sma_cross": (1, "cross", "Golden cross (50-day over 200-day) 3 bars ago"),
    }


def test_unit_sma_evidence_wording_for_bearish_ties_and_no_cross() -> None:
    """TS-SCR-043: below, equal, falling, and no-cross wording."""
    res = FACTOR.compute(snap(95, 95, 100, -0.25, (2, -1), sma20=97), CTX)
    ev = evidence_by_name(res)
    assert ev["close_vs_sma_200"][2] == "Close 95.00 is below the 200-day average 100.00"
    assert ev["close_vs_sma_50"][2] == "Close 95.00 is equal to the 50-day average 95.00"
    assert (
        ev["sma_50_vs_sma_200"][2] == "The 50-day average 95.00 is below the 200-day average 100.00"
    )
    assert ev["sma_20_slope"][2] == "The 20-day average 97.00 fell 0.25 over 5 bars"
    assert ev["sma_cross"][2] == "Death cross (50-day under 200-day) 2 bars ago"
    flat = evidence_by_name(FACTOR.compute(snap(), CTX))
    assert flat["sma_20_slope"][2] == "The 20-day average 100.00 was flat over 5 bars"
    assert flat["sma_cross"] == (0, "cross", "No 50/200-day cross in the last 10 bars")


def test_unit_sma_missing_slope_is_degraded_and_scores_the_rest() -> None:
    """TS-SCR-325: a null slope adds 0 and flags the factor degraded."""
    res = FACTOR.compute(snap(105, 100, 100, slope20=None), CTX)
    assert res.quality is Quality.DEGRADED
    assert res.score == pytest.approx(50.0)
    assert evidence_by_name(res)["sma_20_slope"][0] is None


@pytest.mark.parametrize("field", ["close", "sma_50", "sma_200"])
def test_unit_sma_missing_averages_return_missing(field: str) -> None:
    """TS-SCR-325: a null close or average (history shorter than 200 bars) is missing, score 0."""
    snapshot = snap(105, 100, 100)
    snapshot["daily"][field] = None
    res = FACTOR.compute(snapshot, CTX)
    assert res.quality is Quality.MISSING
    assert res.score == 0
    assert res.reasons == ("The moving averages are not available (not enough history)",)


def test_unit_sma_absent_keys_return_missing() -> None:
    """TS-SCR-325: a snapshot without the daily block is missing, not an exception."""
    assert FACTOR.compute({}, CTX).quality is Quality.MISSING
