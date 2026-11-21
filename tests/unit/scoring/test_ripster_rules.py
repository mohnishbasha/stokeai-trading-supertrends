# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Ripster rules outside the score: confidence deduction, selection gate, evidence block.

Spec: BUILD_PROMPT Factor 12 (FR-333 to FR-335), Confidence, Selection rules, and the evidence
document (S3-T14). S3-T05, S3-T06 and S3-T08 call these helpers.
"""

import copy
import json
from datetime import date
from typing import Any

import pytest

from supertrends.indicators.registry import Bundle
from supertrends.scoring.ripster_rules import (
    confidence_stack_penalty,
    ripster_evidence,
    selection_bias_gate,
)
from supertrends.scoring.snapshot import compute_snapshot
from tests.unit.indicators.lookahead_support import make_bundle
from tests.unit.scoring.ripster_support import config_with, default_config, snapshot

CFG = default_config()

# --- confidence: - 10 if rc_stack == -st_dir_d ------------------------------------------------


@pytest.mark.parametrize(
    ("scenario", "stack", "st_dir_d", "expected"),
    [
        ("TS-SCR-430", 1.0, -1.0, 10.0),  # stack up, Supertrend down: opposes
        ("TS-SCR-430", -1.0, 1.0, 10.0),  # stack down, Supertrend up: opposes
        ("TS-SCR-431", 1.0, 1.0, 0.0),  # same sign
        ("TS-SCR-431", -1.0, -1.0, 0.0),  # same sign
        ("TS-SCR-431", 0.0, 1.0, 0.0),  # stack 0 is never -st_dir_d
        ("TS-SCR-431", 0.0, -1.0, 0.0),
    ],
)
def test_unit_confidence_stack_penalty_rule_lines(
    scenario: str, stack: float, st_dir_d: float, expected: float
) -> None:
    """TS-SCR-430, TS-SCR-431: the deduction is 10 exactly when rc_stack == -st_dir_d."""
    assert confidence_stack_penalty(snapshot(stack=stack, st_dir_d=st_dir_d), CFG) == expected


def test_unit_confidence_stack_penalty_reads_amount_from_config() -> None:
    """TS-SCR-432: `ripster.confidence_stack_conflict_penalty` sets the deduction (15 here)."""
    cfg = config_with(confidence_stack_conflict_penalty=15)
    assert confidence_stack_penalty(snapshot(stack=1.0, st_dir_d=-1.0), cfg) == 15.0
    assert confidence_stack_penalty(snapshot(stack=1.0, st_dir_d=1.0), cfg) == 0.0


@pytest.mark.parametrize(("stack", "st_dir_d"), [(None, -1.0), (1.0, None), (None, None)])
def test_unit_confidence_stack_penalty_null_input_gives_no_deduction(
    stack: float | None, st_dir_d: float | None
) -> None:
    """TS-SCR-433: an undefined stack (warm-up) or direction never deducts."""
    assert confidence_stack_penalty(snapshot(stack=stack, st_dir_d=st_dir_d), CFG) == 0.0


# --- selection: rc_bias gate ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scenario", "side", "bias", "passed", "reason"),
    [
        # Buy needs rc_bias >= 0: below the cloud (-1) rejects; inside (0) and above (+1) pass.
        ("TS-SEL-150", "buy", -1.0, False, "close below the 34/50 cloud"),
        ("TS-SEL-151", "buy", 0.0, True, None),
        ("TS-SEL-152", "buy", 1.0, True, None),
        # Sell needs rc_bias <= 0: above (+1) rejects, inside (0) and below (-1) pass.
        ("TS-SEL-153", "sell", 1.0, False, "close above the 34/50 cloud"),
        ("TS-SEL-154", "sell", 0.0, True, None),
        ("TS-SEL-155", "sell", -1.0, True, None),
    ],
)
def test_unit_selection_bias_gate_rule_lines(
    scenario: str, side: str, bias: float, passed: bool, reason: str | None
) -> None:
    """TS-SEL-150 to TS-SEL-155: the gate on both sides, rejection reason recorded."""
    assert selection_bias_gate(snapshot(bias=bias), side, CFG) == (passed, reason)  # type: ignore[arg-type]


def test_unit_selection_bias_gate_disabled_passes_everything() -> None:
    """TS-SEL-156: `ripster.selection_bias_gate: false` disables the gate on both sides."""
    cfg = config_with(selection_bias_gate=False)
    assert selection_bias_gate(snapshot(bias=-1.0), "buy", cfg) == (True, None)
    assert selection_bias_gate(snapshot(bias=1.0), "sell", cfg) == (True, None)


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_unit_selection_bias_gate_null_bias_fails_closed_with_reason(side: str) -> None:
    """TS-SEL-157: an undefined bias (under 50 bars) rejects with a recorded reason."""
    passed, reason = selection_bias_gate(snapshot(bias=None), side, CFG)  # type: ignore[arg-type]
    assert passed is False
    assert reason == "34/50 cloud bias not available"


def test_unit_selection_bias_gate_unknown_side_raises() -> None:
    """TS-SEL-158: a side other than buy or sell is a programming error."""
    with pytest.raises(ValueError, match="side"):
        selection_bias_gate(snapshot(), "hold", CFG)  # type: ignore[arg-type]


def test_unit_selection_bias_gate_does_not_read_other_fields_or_mutate() -> None:
    """TS-SEL-159: the verdict depends on `ripster.bias` only and leaves the snapshot intact."""
    snap = snapshot(bias=-1.0, stack=1.0, pullback=1.0, st_dir_d=-1.0)
    before = copy.deepcopy(snap)
    assert selection_bias_gate(snap, "buy", CFG)[0] is False
    assert selection_bias_gate(snapshot(bias=-1.0), "buy", CFG)[0] is False
    assert snap == before


# --- evidence: the `ripster` block ------------------------------------------------------------


def test_unit_evidence_ripster_block_has_exactly_the_spec_keys_with_integer_signs() -> None:
    """TS-NAR-150: keys bias, stack, bars_since_stack_flip, c2_dir, c3_dir, c3_top, c3_bot, dir_w,
    as in the BUILD_PROMPT evidence example; signs and the flip count are integers."""
    block = ripster_evidence(
        snapshot(bias=1.0, stack=1.0, bars_since_stack_flip=12.0, c2_dir=1.0, c3_dir=1.0)
    )
    assert block == {
        "bias": 1,
        "stack": 1,
        "bars_since_stack_flip": 12,
        "c2_dir": 1,
        "c3_dir": 1,
        "c3_top": 210.8,
        "c3_bot": 206.3,
        "dir_w": 1,
    }
    for key in ("bias", "stack", "bars_since_stack_flip", "c2_dir", "c3_dir", "dir_w"):
        assert type(block[key]) is int, key


def test_unit_evidence_ripster_block_bearish_values() -> None:
    """TS-NAR-151: negative signs stay negative integers; zero stack stays 0."""
    block = ripster_evidence(
        snapshot(
            bias=-1.0, stack=0.0, c2_dir=-1.0, c3_dir=-1.0, dir_w=-1.0, bars_since_stack_flip=0.0
        )
    )
    assert (block["bias"], block["stack"], block["c2_dir"], block["c3_dir"], block["dir_w"]) == (
        -1,
        0,
        -1,
        -1,
        -1,
    )
    assert block["bars_since_stack_flip"] == 0


def test_unit_evidence_ripster_block_null_fields_stay_null_never_zero() -> None:
    """TS-NAR-152: null in the snapshot (no flip count, no weekly history) stays None."""
    block = ripster_evidence(
        snapshot(
            bias=None, stack=None, bars_since_stack_flip=None, dir_w=None, c3_top=None, c3_bot=None
        )
    )
    for key in ("bias", "stack", "bars_since_stack_flip", "dir_w", "c3_top", "c3_bot"):
        assert block[key] is None, key


def test_unit_evidence_ripster_block_is_json_serializable_and_pure() -> None:
    """TS-NAR-153: plain JSON types; the input snapshot is not modified or aliased."""
    snap = snapshot(bias=1.0, stack=1.0, bars_since_stack_flip=4.0)
    before = copy.deepcopy(snap)
    block = ripster_evidence(snap)
    assert json.loads(json.dumps(block, allow_nan=False)) == block
    assert snap == before
    block["bias"] = 99
    assert snap == before


@pytest.fixture(scope="module")
def bundle() -> Bundle:
    return make_bundle(seed=7, n=420, intraday_from=400)


def test_unit_evidence_ripster_block_from_computed_snapshot_matches_its_fields(
    bundle: Bundle,
) -> None:
    """TS-NAR-154: on a real snapshot every key equals the matching snapshot field."""
    doc: dict[str, Any] = compute_snapshot(bundle, CFG, date.fromisoformat(str(bundle.dates[-1])))
    r = doc["ripster"]
    block = ripster_evidence(doc)
    assert set(block) == {
        "bias",
        "stack",
        "bars_since_stack_flip",
        "c2_dir",
        "c3_dir",
        "c3_top",
        "c3_bot",
        "dir_w",
    }
    assert block["c3_top"] == r["c3_top"]
    assert block["c3_bot"] == r["c3_bot"]
    assert block["c3_top"] >= block["c3_bot"]
    for key in ("bias", "stack", "c2_dir", "c3_dir", "dir_w"):
        assert block[key] == r[key]
    assert (block["bars_since_stack_flip"] is None) == (r["bars_since_stack_flip"] is None)
