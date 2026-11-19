# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 4, RSI, MACD and OBV divergence: rule lines, both signs (S3-T02; TS-SCR-070 to 080)."""

from __future__ import annotations

from typing import Any

import pytest

from supertrends.scoring.factor import Quality
from supertrends.scoring.factors.divergence import FACTOR
from tests.unit.scoring.factor_support import context, evidence_by_name, load_cfg

CFG = load_cfg()
CTX = context(CFG)
BARS = 300  # daily bars in the snapshot
WEEKS = 60  # weekly bars in the snapshot


def rec(
    osc: str,
    kind: str,
    side: str,
    ago: int = 5,
    timeframe: str = "daily",
) -> dict[str, Any]:
    """A divergence record (the shape of `indicators.divergence.Divergence` in the snapshot).

    `ago` is bars between the second pivot and the as-of bar (`t - p2`). Prices and oscillator
    values are fixed so the wording is predictable.
    """
    n = BARS if timeframe == "daily" else WEEKS
    p2 = n - 1 - ago
    return {
        "kind": kind,
        "side": side,
        "oscillator": osc,
        "timeframe": timeframe,
        "p1": p2 - 20,
        "p2": p2,
        "price1": 50.0,
        "price2": 48.0,
        "osc1": 30.0,
        "osc2": 35.0,
        "confirmed_at": p2 + 5,
    }


def snap(daily: list[dict[str, Any]], weekly: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "bars": BARS,
        "weekly": {"weeks": WEEKS},
        "divergences": {"daily": daily, "weekly": weekly or []},
    }


RB, RS = ("regular", "bullish"), ("regular", "bearish")
HB, HS = ("hidden", "bullish"), ("hidden", "bearish")

# Hand sums: RSI +-40, MACD histogram +-35, OBV +-25 (sign by side, hidden at half value); then
# x1.25 once when the same oscillator, kind and side also exists on weekly bars; clip to +-100.
RULE_ROWS = [
    # TS-SCR-070: regular bullish RSI +40
    pytest.param([rec("rsi", *RB)], [], 40.0, id="TS-SCR-070-regular-bullish-rsi"),
    # TS-SCR-071: regular bearish RSI -40
    pytest.param([rec("rsi", *RS)], [], -40.0, id="TS-SCR-071-regular-bearish-rsi"),
    # TS-SCR-072: regular bullish MACD histogram +35 (and the bearish mirror -35)
    pytest.param([rec("macd_hist", *RB)], [], 35.0, id="TS-SCR-072-regular-bullish-macd-hist"),
    pytest.param([rec("macd_hist", *RS)], [], -35.0, id="TS-SCR-072-regular-bearish-macd-hist"),
    # TS-SCR-073: regular bullish OBV +25 (and -25)
    pytest.param([rec("obv", *RB)], [], 25.0, id="TS-SCR-073-regular-bullish-obv"),
    pytest.param([rec("obv", *RS)], [], -25.0, id="TS-SCR-073-regular-bearish-obv"),
    # TS-SCR-074: hidden bullish RSI counts at half: 40 * 0.5
    pytest.param([rec("rsi", *HB)], [], 20.0, id="TS-SCR-074-hidden-bullish-rsi"),
    # hidden bearish RSI and MACD histogram: -20, -17.5
    pytest.param([rec("rsi", *HS)], [], -20.0, id="TS-SCR-074-hidden-bearish-rsi"),
    pytest.param([rec("macd_hist", *HB)], [], 17.5, id="TS-SCR-074-hidden-bullish-macd-hist"),
    # TS-SCR-075: hidden bearish OBV: -25 * 0.5
    pytest.param([rec("obv", *HS)], [], -12.5, id="TS-SCR-075-hidden-bearish-obv"),
    # TS-SCR-076: the same type on weekly bars multiplies the total: 40 * 1.25
    pytest.param(
        [rec("rsi", *RB)],
        [rec("rsi", *RB, ago=3, timeframe="weekly")],
        50.0,
        id="TS-SCR-076-weekly",
    ),
    # bearish: -40 * 1.25
    pytest.param(
        [rec("rsi", *RS)],
        [rec("rsi", *RS, ago=3, timeframe="weekly")],
        -50.0,
        id="TS-SCR-076-weekly-bearish",
    ),
    # a hidden daily with a hidden weekly of the same type: 20 * 1.25
    pytest.param(
        [rec("rsi", *HB)],
        [rec("rsi", *HB, ago=3, timeframe="weekly")],
        25.0,
        id="TS-SCR-076-hidden",
    ),
    # a different type on weekly (regular bearish RSI vs daily regular bullish RSI) does not count
    pytest.param(
        [rec("rsi", *RB)],
        [rec("rsi", *RS, ago=3, timeframe="weekly")],
        40.0,
        id="TS-SCR-076-other-side",
    ),
    # a different kind (hidden bullish RSI weekly vs regular bullish RSI daily) does not count
    pytest.param(
        [rec("rsi", *RB)],
        [rec("rsi", *HB, ago=3, timeframe="weekly")],
        40.0,
        id="TS-SCR-076-other-kind",
    ),
    # a different oscillator (OBV weekly vs RSI daily) does not count
    pytest.param(
        [rec("rsi", *RB)],
        [rec("obv", *RB, ago=3, timeframe="weekly")],
        40.0,
        id="TS-SCR-076-other-osc",
    ),
    # weekly with no daily divergence adds nothing
    pytest.param(
        [], [rec("rsi", *RB, ago=3, timeframe="weekly")], 0.0, id="TS-SCR-076-weekly-only"
    ),
    # two daily divergences both confirmed weekly: the multiplier applies once to the total:
    # (40 + 35) * 1.25 = 93.75
    pytest.param(
        [rec("rsi", *RB), rec("macd_hist", *RB)],
        [
            rec("rsi", *RB, ago=3, timeframe="weekly"),
            rec("macd_hist", *RB, ago=3, timeframe="weekly"),
        ],
        93.75,
        id="TS-SCR-076-multiplier-once",
    ),
    # only one of the two confirmed: still (40 + 35) * 1.25, the multiplier is on the total
    pytest.param(
        [rec("rsi", *RB), rec("macd_hist", *RB)],
        [rec("rsi", *RB, ago=3, timeframe="weekly")],
        93.75,
        id="TS-SCR-076-multiplier-on-total",
    ),
    # TS-SCR-077: 40 + 35 + 25 = 100 exactly; with weekly 100 * 1.25 = 125 clips to 100
    pytest.param(
        [rec("rsi", *RB), rec("macd_hist", *RB), rec("obv", *RB)], [], 100.0, id="TS-SCR-077-cap"
    ),
    pytest.param(
        [rec("rsi", *RB), rec("macd_hist", *RB), rec("obv", *RB)],
        [rec("obv", *RB, ago=3, timeframe="weekly")],
        100.0,
        id="TS-SCR-077-clipped-125",
    ),
    pytest.param(
        [rec("rsi", *RS), rec("macd_hist", *RS), rec("obv", *RS)],
        [rec("obv", *RS, ago=3, timeframe="weekly")],
        -100.0,
        id="TS-SCR-077-clipped-minus-125",
    ),
    # TS-SCR-078: none present
    pytest.param([], [], 0.0, id="TS-SCR-078-none"),
    # TS-SCR-079: bullish RSI +40 and bearish OBV -25 net to +15 (bullish low and bearish high)
    pytest.param([rec("rsi", *RB), rec("obv", *RS)], [], 15.0, id="TS-SCR-079-net-out"),
    # the same oscillator can be bullish (pivot lows) and bearish (pivot highs): 40 - 40 = 0
    pytest.param([rec("rsi", *RB), rec("rsi", *RS)], [], 0.0, id="TS-SCR-079-same-osc-both-sides"),
    # a net total is multiplied: (40 - 25) * 1.25 = 18.75
    pytest.param(
        [rec("rsi", *RB), rec("obv", *RS)],
        [rec("rsi", *RB, ago=2, timeframe="weekly")],
        18.75,
        id="TS-SCR-079-net-then-weekly",
    ),
    # TS-SCR-080: second pivot 15 bars back counts (t - p2 = 15), 16 does not
    pytest.param([rec("rsi", *RB, ago=15)], [], 40.0, id="TS-SCR-080-15-bars-counts"),
    pytest.param([rec("rsi", *RB, ago=16)], [], 0.0, id="TS-SCR-080-16-bars-not-counted"),
    pytest.param([rec("rsi", *RB, ago=0)], [], 40.0, id="TS-SCR-080-0-bars-counts"),
    # an expired record does not make the weekly record count, and an expired weekly one is ignored
    pytest.param(
        [rec("rsi", *RB)],
        [rec("rsi", *RB, ago=16, timeframe="weekly")],
        40.0,
        id="TS-SCR-080-weekly-16-weeks-ignored",
    ),
    pytest.param(
        [rec("rsi", *RB)],
        [rec("rsi", *RB, ago=15, timeframe="weekly")],
        50.0,
        id="TS-SCR-080-weekly-15-weeks-counts",
    ),
]


@pytest.mark.parametrize(("daily", "weekly", "expected"), RULE_ROWS)
def test_unit_divergence_score_rule_lines(
    daily: list[dict[str, Any]], weekly: list[dict[str, Any]], expected: float
) -> None:
    """TS-SCR-070 to 080: the score for each rule line, both signs, hidden, weekly, boundaries."""
    res = FACTOR.compute(snap(daily, weekly), CTX)
    assert res.factor_id == "divergence"
    assert res.quality is Quality.OK
    assert res.score == pytest.approx(expected)


def test_unit_divergence_points_multipliers_and_recency_follow_the_config() -> None:
    """TS-SCR-074: points, hidden and weekly multipliers, and recency come from the config."""
    dv = CFG.divergence.model_copy(
        update={
            "points": CFG.divergence.points.model_copy(update={"rsi": 10.0}),
            "hidden_multiplier": 0.25,
            "weekly_confirm_multiplier": 2.0,
            "recency_bars": 4,
        }
    )
    ctx = context(CFG.model_copy(update={"divergence": dv}))
    assert FACTOR.compute(snap([rec("rsi", *RB)]), ctx).score == 10.0
    assert FACTOR.compute(snap([rec("rsi", *HB)]), ctx).score == 2.5  # 10 * 0.25
    weekly = [rec("rsi", *RB, ago=1, timeframe="weekly")]
    assert FACTOR.compute(snap([rec("rsi", *RB)], weekly), ctx).score == 20.0  # 10 * 2.0
    assert FACTOR.compute(snap([rec("rsi", *RB, ago=4)]), ctx).score == 10.0
    assert FACTOR.compute(snap([rec("rsi", *RB, ago=5)]), ctx).score == 0.0


def test_unit_divergence_evidence_lists_each_divergence_with_points() -> None:
    """TS-SCR-070: one evidence item per counted divergence, with signed points and a reason."""
    res = FACTOR.compute(snap([rec("rsi", *RB), rec("obv", *HS, ago=9)]), CTX)
    assert evidence_by_name(res) == {
        "rsi_regular_bullish": (
            40.0,
            "points",
            "Regular bullish RSI divergence: price low 50.00 then 48.00 "
            "while RSI went 30.00 then 35.00, 5 bars ago",
        ),
        "obv_hidden_bearish": (
            -12.5,
            "points",
            "Hidden bearish OBV divergence: price high 50.00 then 48.00 "
            "while OBV went 30.00 then 35.00, 9 bars ago",
        ),
    }


def test_unit_divergence_evidence_wording_for_macd_weekly_confirmation_and_none() -> None:
    """TS-SCR-076: MACD histogram wording, the weekly confirmation item, and the empty case."""
    res = FACTOR.compute(
        snap(
            [rec("macd_hist", *RS)],
            [rec("macd_hist", *RS, ago=3, timeframe="weekly")],
        ),
        CTX,
    )
    ev = evidence_by_name(res)
    assert ev["macd_hist_regular_bearish"][0] == -35.0
    assert ev["macd_hist_regular_bearish"][2].startswith(
        "Regular bearish MACD histogram divergence: price high 50.00 then 48.00 while "
    )
    assert ev["weekly_confirmation"] == (
        1.25,
        "multiplier",
        "The same divergence on weekly bars multiplies the total by 1.25",
    )
    none = evidence_by_name(FACTOR.compute(snap([]), CTX))
    assert none == {
        "divergence_count": (
            0,
            "count",
            "No RSI, MACD histogram, or OBV divergence with a second pivot in the last 15 bars",
        )
    }


def test_unit_divergence_without_weekly_confirmation_has_no_multiplier_item() -> None:
    """TS-SCR-076: no weekly match, no multiplier evidence."""
    res = FACTOR.compute(snap([rec("rsi", *RB)], [rec("obv", *RB, ago=3, timeframe="weekly")]), CTX)
    assert "weekly_confirmation" not in evidence_by_name(res)


def test_unit_divergence_unknown_oscillator_is_rejected() -> None:
    """TS-SCR-070: a record the config has no points for is a programming error, not a score."""
    with pytest.raises(ValueError, match="stochastic"):
        FACTOR.compute(snap([rec("stochastic", *RB)]), CTX)


def test_unit_divergence_absent_block_returns_missing() -> None:
    """TS-SCR-078: a snapshot without divergence blocks is missing, score 0, not an exception."""
    res = FACTOR.compute({}, CTX)
    assert res.quality is Quality.MISSING
    assert res.score == 0
    assert res.reasons == ("Divergences are not available",)
