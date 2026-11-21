# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Candidate rules and the Ripster gate (TS-SEL; S3-T06; FR-401, FR-402, FR-334, FR-412).

Seed config: buy display >= 65, sell display <= 35, confidence >= 50, liquidity floor
20,000,000. Expected values are read off the spec by hand, never from the code under test.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any

import pytest

from supertrends.scoring.factor import SELECTION_INPUT_PATHS
from supertrends.selection.candidates import (
    REASON_LIQUIDITY,
    REASON_RC_BUY,
    REASON_RC_SELL,
    REASON_RC_UNAVAILABLE,
    REASON_STALE,
    SelectionInput,
    buy_threshold,
    evaluate_candidate,
    rc_bias_gate,
    selection_input_from_snapshot,
    sell_threshold,
)
from tests.unit.selection.sel_support import buy, card, cfg, sell, with_gate


def _buy_reasons(entry: SelectionInput) -> tuple[str, ...]:
    return evaluate_candidate(entry, cfg()).buy.reasons


def _sell_reasons(entry: SelectionInput) -> tuple[str, ...]:
    return evaluate_candidate(entry, cfg()).sell.reasons


# --- buy rule lines (TS-SEL-001 to TS-SEL-010) -----------------------------------------------


def test_unit_selection_buy_candidate_all_conditions_met_qualifies() -> None:
    """TS-SEL-001: display 70, st_dir_d +1, confidence 60, ok, 25M (FR-401 first case) -> buy."""
    check = evaluate_candidate(buy("ORCL", 70.0, confidence=60.0, adv=25_000_000.0), cfg())
    assert check.buy.qualified
    assert check.buy.reasons == ()
    assert check.buy.threshold == 65.0
    assert not check.sell.qualified  # 70 is above the sell threshold of 35


@pytest.mark.parametrize(
    ("display", "qualified"),
    [
        pytest.param(64.9, False, id="TS-SEL-002-64.9"),
        pytest.param(65.0, True, id="TS-SEL-003-65.0"),
    ],
)
def test_unit_selection_buy_candidate_display_boundary(display: float, qualified: bool) -> None:
    """TS-SEL-002, TS-SEL-003: display 64.9 misses the buy bar of 65; 65.0 meets it (>=)."""
    reasons = _buy_reasons(buy("A", display))
    assert (reasons == ()) is qualified
    if not qualified:
        assert reasons == ("score below the buy threshold of 65",)


def test_unit_selection_buy_candidate_st_dir_down_not_qualified() -> None:
    """TS-SEL-004: st_dir_d -1 fails the direction rule; reason names the direction."""
    assert _buy_reasons(buy("A", st_dir_d=-1)) == ("Supertrend direction is down",)


@pytest.mark.parametrize(
    ("confidence", "reasons"),
    [
        pytest.param(49.0, ("confidence 49 below 50",), id="TS-SEL-005-49"),
        pytest.param(50.0, (), id="TS-SEL-006-50"),
    ],
)
def test_unit_selection_buy_candidate_confidence_boundary(
    confidence: float, reasons: tuple[str, ...]
) -> None:
    """TS-SEL-005, TS-SEL-006: confidence 49 fails (needs >= 50); 50 passes."""
    assert _buy_reasons(buy("A", confidence=confidence)) == reasons


def test_unit_selection_buy_candidate_stale_data_not_qualified() -> None:
    """TS-SEL-007: data quality `stale` fails even with everything else met (ADR-045)."""
    assert _buy_reasons(buy("A", quality="stale")) == (REASON_STALE,)


@pytest.mark.parametrize(
    ("adv", "reasons"),
    [
        pytest.param(19_999_999.0, (REASON_LIQUIDITY,), id="TS-SEL-008-below"),
        pytest.param(20_000_000.0, (), id="TS-SEL-009-exactly"),
    ],
)
def test_unit_selection_buy_candidate_dollar_volume_floor(
    adv: float, reasons: tuple[str, ...]
) -> None:
    """TS-SEL-008, TS-SEL-009: 19,999,999 is below the 20,000,000 floor; exactly 20M passes."""
    assert _buy_reasons(buy("A", adv=adv)) == reasons


@pytest.mark.parametrize(
    ("display", "qualified"), [(74.9, False), (75.0, True)], ids=["74.9", "75.0"]
)
def test_unit_selection_buy_candidate_threshold_adjustments_raise_bar_to_75(
    display: float, qualified: bool
) -> None:
    """TS-SEL-010: shifts of +5 (risk_off) and +5 (weak fundamentals) give 65 + 10 = 75."""
    entry = buy("A", display, buy_shift=10.0)
    assert buy_threshold(entry, cfg()) == 75.0
    reasons = _buy_reasons(entry)
    assert (reasons == ()) is qualified
    if not qualified:
        assert reasons == ("score below the buy threshold of 75",)


def test_unit_selection_buy_candidate_fr401_risk_off_example() -> None:
    """TS-SEL-010: FR-401 example, display 69 under risk_off (65 + 5 = 70) is not a buy."""
    assert _buy_reasons(buy("A", 69.0, buy_shift=5.0)) == ("score below the buy threshold of 70",)


# --- sell rule lines (TS-SEL-011 to TS-SEL-015) ----------------------------------------------


def test_unit_selection_sell_candidate_all_conditions_met_qualifies() -> None:
    """TS-SEL-011: FR-402 first case, display 33, st_dir_d -1, confidence 55, 50M -> sell."""
    check = evaluate_candidate(sell("X", 33.0, confidence=55.0, adv=50_000_000.0), cfg())
    assert check.sell.qualified
    assert check.sell.threshold == 35.0
    assert not check.buy.qualified


@pytest.mark.parametrize(
    ("display", "reasons"),
    [
        pytest.param(35.0, (), id="TS-SEL-012-35.0"),
        pytest.param(35.1, ("score above the sell threshold of 35",), id="TS-SEL-013-35.1"),
    ],
)
def test_unit_selection_sell_candidate_display_boundary(
    display: float, reasons: tuple[str, ...]
) -> None:
    """TS-SEL-012, TS-SEL-013: 35.0 meets the sell bar (<=); 35.1 misses it."""
    assert _sell_reasons(sell("X", display)) == reasons


def test_unit_selection_sell_candidate_st_dir_up_not_qualified() -> None:
    """TS-SEL-014: st_dir_d +1 fails the sell direction rule."""
    assert _sell_reasons(sell("X", st_dir_d=1)) == ("Supertrend direction is up",)


@pytest.mark.parametrize(
    ("display", "qualified"), [(25.0, True), (25.1, False)], ids=["25.0", "25.1"]
)
def test_unit_selection_sell_candidate_threshold_adjustments_lower_bar_to_25(
    display: float, qualified: bool
) -> None:
    """TS-SEL-015: shifts of -5 (risk_on) and -5 (strong fundamentals) give 35 - 10 = 25."""
    entry = sell("X", display, sell_shift=10.0)
    assert sell_threshold(entry, cfg()) == 25.0
    reasons = _sell_reasons(entry)
    assert (reasons == ()) is qualified
    if not qualified:
        assert reasons == ("score above the sell threshold of 25",)


def test_unit_selection_sell_candidate_mirror_rules_confidence_stale_liquidity() -> None:
    """TS-SEL-011: the last three rules are shared; each fails a sell on its own."""
    assert _sell_reasons(sell("X", confidence=49.0)) == ("confidence 49 below 50",)
    assert _sell_reasons(sell("X", quality="stale")) == (REASON_STALE,)
    assert _sell_reasons(sell("X", adv=19_999_999.0)) == (REASON_LIQUIDITY,)


# --- Ripster gate (TS-SEL-039 to TS-SEL-044) -------------------------------------------------


@pytest.mark.parametrize(
    ("side", "rc_bias", "passed", "reason"),
    [
        pytest.param("buy", -1, False, "close below the 34/50 cloud", id="TS-SEL-039"),
        pytest.param("buy", 0, True, None, id="TS-SEL-040"),
        pytest.param("buy", 1, True, None, id="TS-SEL-041"),
        pytest.param("sell", 1, False, "close above the 34/50 cloud", id="TS-SEL-042"),
        pytest.param("sell", 0, True, None, id="TS-SEL-043"),
        pytest.param("sell", -1, True, None, id="TS-SEL-044"),
    ],
)
def test_unit_selection_rc_bias_gate_rule_lines(
    side: Any, rc_bias: int, passed: bool, reason: str | None
) -> None:
    """TS-SEL-039 to TS-SEL-044: buy needs rc_bias >= 0, sell needs rc_bias <= 0; 0 passes both."""
    assert rc_bias_gate(rc_bias, side, cfg()) == (passed, reason)


def test_unit_selection_buy_candidate_rc_bias_minus_1_not_qualified_reason_close_below_34_50_cloud() -> (  # noqa: E501
    None
):
    """TS-SEL-039: FR-401 first case with rc_bias -1 is not a buy; the reason is recorded."""
    assert _buy_reasons(buy("A", rc_bias=-1)) == (REASON_RC_BUY,)


def test_unit_selection_buy_candidate_rc_bias_0_close_inside_34_50_cloud_qualifies() -> None:
    """TS-SEL-040: close inside the 34/50 cloud (rc_bias 0) passes the buy gate."""
    assert _buy_reasons(buy("A", rc_bias=0)) == ()


def test_unit_selection_buy_candidate_rc_bias_plus_1_passes_ripster_gate() -> None:
    """TS-SEL-041: close above the cloud passes the buy gate."""
    assert _buy_reasons(buy("A", rc_bias=1)) == ()


def test_unit_selection_sell_candidate_rc_bias_plus_1_not_qualified_reason_close_above_34_50_cloud() -> (  # noqa: E501
    None
):
    """TS-SEL-042: FR-402 first case with rc_bias +1 is not a sell; the reason is recorded."""
    assert _sell_reasons(sell("X", rc_bias=1)) == (REASON_RC_SELL,)


def test_unit_selection_sell_candidate_rc_bias_0_close_inside_34_50_cloud_qualifies() -> None:
    """TS-SEL-043: close inside the cloud passes the sell gate."""
    assert _sell_reasons(sell("X", rc_bias=0)) == ()


def test_unit_selection_sell_candidate_rc_bias_minus_1_passes_ripster_gate() -> None:
    """TS-SEL-044: close below the cloud passes the sell gate."""
    assert _sell_reasons(sell("X", rc_bias=-1)) == ()


# --- added scenarios (TS-SEL-101 to TS-SEL-104) ----------------------------------------------


def _snapshot(**over: Any) -> dict[str, Any]:
    values = {
        "st": 1.0,
        "bias": 0.0,
        "adv": 3.0e7,
        "rv": 1.4,
        "flip": 5.0,
    } | over
    return {
        "daily": {
            "supertrend": {"direction": values["st"]},
            "avg_dollar_volume_20d": values["adv"],
            "relative_volume": values["rv"],
            "bars_since_flip": values["flip"],
        },
        "ripster": {"bias": values["bias"]},
    }


def test_unit_selection_input_from_snapshot_reads_selection_input_paths() -> None:
    """TS-SEL-101: the builder reads exactly `SELECTION_INPUT_PATHS`, ints for signs and counts."""
    assert set(SELECTION_INPUT_PATHS) == {
        "daily.supertrend.direction",
        "ripster.bias",
        "daily.avg_dollar_volume_20d",
        "daily.relative_volume",
        "daily.bars_since_flip",
    }
    c = card(70.0, 60.0)
    entry = selection_input_from_snapshot(
        "ORCL", c, _snapshot(), data_quality="degraded", buy_threshold_shift=5.0
    )
    assert entry == SelectionInput(
        ticker="ORCL",
        card=c,
        st_dir_d=1,
        rc_bias=0,
        bars_since_flip=5,
        relative_volume=1.4,
        avg_dollar_volume_20d=3.0e7,
        data_quality="degraded",
        buy_threshold_shift=5.0,
        sell_threshold_shift=0.0,
    )
    assert isinstance(entry.st_dir_d, int)
    assert isinstance(entry.bars_since_flip, int)
    assert entry.display_score == 70.0
    assert entry.confidence == 60.0


def test_unit_selection_input_from_snapshot_null_and_nan_become_none() -> None:
    """TS-SEL-101: a null or NaN snapshot value (warm-up) becomes None, never 0."""
    entry = selection_input_from_snapshot(
        "A", card(70.0, 60.0), _snapshot(st=None, bias=math.nan, adv=None, rv=math.nan, flip=None)
    )
    assert entry.st_dir_d is None
    assert entry.rc_bias is None
    assert entry.avg_dollar_volume_20d is None
    assert entry.relative_volume is None
    assert entry.bars_since_flip is None


def test_unit_selection_input_from_snapshot_missing_path_raises_key_error() -> None:
    """TS-SEL-101: an absent snapshot path is a KeyError naming it (not a silent pass)."""
    snap = _snapshot()
    del snap["ripster"]
    with pytest.raises(KeyError, match=r"ripster\.bias"):
        selection_input_from_snapshot("A", card(70.0, 60.0), snap)


def test_unit_selection_candidate_reasons_in_rule_order() -> None:
    """TS-SEL-102: every failing rule is listed, in the order of the selection rules."""
    entry = buy(
        "A", 60.0, st_dir_d=-1, rc_bias=-1, confidence=40.0, quality="stale", adv=1_000_000.0
    )
    assert _buy_reasons(entry) == (
        "score below the buy threshold of 65",
        "Supertrend direction is down",
        REASON_RC_BUY,
        "confidence 40 below 50",
        REASON_STALE,
        REASON_LIQUIDITY,
    )
    worst_sell = sell("X", 60.0, st_dir_d=1, rc_bias=1, confidence=40.0, quality="stale", adv=None)
    assert _sell_reasons(worst_sell) == (
        "score above the sell threshold of 35",
        "Supertrend direction is up",
        REASON_RC_SELL,
        "confidence 40 below 50",
        REASON_STALE,
        REASON_LIQUIDITY,
    )


def test_unit_selection_candidate_null_inputs_fail_with_reasons() -> None:
    """TS-SEL-103: null direction, bias or dollar volume fail closed with a reason."""
    assert _buy_reasons(buy("A", st_dir_d=None)) == ("Supertrend direction not available",)
    assert _sell_reasons(sell("X", st_dir_d=None)) == ("Supertrend direction not available",)
    assert _buy_reasons(buy("A", rc_bias=None)) == (REASON_RC_UNAVAILABLE,)
    assert _buy_reasons(buy("A", adv=None)) == (REASON_LIQUIDITY,)


def test_unit_selection_confidence_reason_formats_fraction() -> None:
    """TS-SEL-103: an unrounded confidence prints with up to two decimals: 49.96 -> "49.96"."""
    assert _buy_reasons(buy("A", confidence=49.96)) == ("confidence 49.96 below 50",)


def test_unit_selection_rc_bias_gate_disabled_and_unknown_side() -> None:
    """TS-SEL-104: `ripster.selection_bias_gate: false` passes everything; a bad side raises."""
    off = with_gate(cfg(), enabled=False)
    assert rc_bias_gate(-1, "buy", off) == (True, None)
    assert rc_bias_gate(1, "sell", off) == (True, None)
    assert rc_bias_gate(None, "buy", off) == (True, None)
    assert evaluate_candidate(buy("A", rc_bias=-1), off).buy.qualified
    assert rc_bias_gate(None, "sell", cfg()) == (False, REASON_RC_UNAVAILABLE)
    with pytest.raises(ValueError, match="side"):
        rc_bias_gate(0, "short", cfg())  # type: ignore[arg-type]


def test_unit_selection_candidate_check_side_accessor() -> None:
    """TS-SEL-104: `CandidateCheck.side` returns the matching side and rejects others."""
    check = evaluate_candidate(buy("A"), cfg())
    assert check.side("buy") is check.buy
    assert check.side("sell") is check.sell
    with pytest.raises(ValueError, match="side"):
        check.side("hold")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "over",
    [
        {"ticker": ""},
        {"buy_threshold_shift": -1.0},
        {"sell_threshold_shift": -0.5},
        {"buy_threshold_shift": math.inf},
    ],
)
def test_unit_selection_input_validation(over: dict[str, Any]) -> None:
    """TS-SEL-104: an empty ticker or a negative or non-finite shift is a ValueError."""
    with pytest.raises(ValueError, match=r"ticker|shift"):
        dataclasses.replace(buy("A"), **over)
