# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Ripster rules outside the factor score (Signal Engine Specification, Factor 12; S3-T14).

Pure helpers over the indicator snapshot (`scoring.snapshot.compute_snapshot`) and the validated
config, for the tasks that own the composite, selection and evidence modules:

* `confidence_stack_penalty` is the confidence rule "- 10 if rc_stack == -st_dir_d" (FR-335); the
  amount is `ripster.confidence_stack_conflict_penalty`. S3-T05 subtracts it and shows the
  deduction.
* `selection_bias_gate` is the selection rule `rc_bias >= 0` for buys and `rc_bias <= 0` for
  sells (FR-334), switched by `ripster.selection_bias_gate`. S3-T06 calls it per candidate and
  records the reason.
* `ripster_evidence` builds the `ripster` block of the evidence document. S3-T08 embeds it.

Nothing here reads a clock, I/O, or LLM output, and nothing mutates its arguments.
"""

from collections.abc import Mapping
from typing import Any, Literal

from supertrends.scoring.config import ScoringConfig
from supertrends.scoring.factor import get_path

__all__ = [
    "REJECT_BUY_REASON",
    "REJECT_SELL_REASON",
    "REJECT_UNAVAILABLE_REASON",
    "Side",
    "confidence_stack_penalty",
    "ripster_evidence",
    "selection_bias_gate",
]

Side = Literal["buy", "sell"]

REJECT_BUY_REASON = "close below the 34/50 cloud"
REJECT_SELL_REASON = "close above the 34/50 cloud"
REJECT_UNAVAILABLE_REASON = "34/50 cloud bias not available"

_EVIDENCE_SIGNS = ("bias", "stack", "bars_since_stack_flip", "c2_dir", "c3_dir", "dir_w")
_EVIDENCE_PRICES = ("c3_top", "c3_bot")


def _opt(snapshot: Mapping[str, Any], path: str) -> float | None:
    value = get_path(snapshot, path)
    return None if value is None else float(value)


def confidence_stack_penalty(snapshot: Mapping[str, Any], config: ScoringConfig) -> float:
    """The confidence deduction when the Ripster stack opposes the daily Supertrend.

    Returns `ripster.confidence_stack_conflict_penalty` when `rc_stack == -st_dir_d` with a
    nonzero stack, else 0.0. A null stack or direction (warm-up) deducts nothing.
    """
    stack = _opt(snapshot, "ripster.stack")
    st_dir_d = _opt(snapshot, "daily.supertrend.direction")
    if stack is None or st_dir_d is None or stack == 0:
        return 0.0
    if stack == -st_dir_d:
        return float(config.ripster.confidence_stack_conflict_penalty)
    return 0.0


def selection_bias_gate(
    snapshot: Mapping[str, Any], side: Side, config: ScoringConfig
) -> tuple[bool, str | None]:
    """The `rc_bias` selection gate: `(passed, reason)`; reason is None when passed.

    A buy is rejected when the close is below the 34/50 cloud (`rc_bias < 0`), a sell when it is
    above (`rc_bias > 0`); inside the cloud passes both. With `ripster.selection_bias_gate`
    false everything passes. An undefined bias (fewer than 50 bars) fails closed with a reason.
    Raises ValueError for a side other than "buy" or "sell".
    """
    if side not in ("buy", "sell"):
        msg = f"side must be 'buy' or 'sell', got {side!r}"
        raise ValueError(msg)
    if not config.ripster.selection_bias_gate:
        return True, None
    bias = _opt(snapshot, "ripster.bias")
    if bias is None:
        return False, REJECT_UNAVAILABLE_REASON
    if side == "buy" and bias < 0:
        return False, REJECT_BUY_REASON
    if side == "sell" and bias > 0:
        return False, REJECT_SELL_REASON
    return True, None


def ripster_evidence(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """The `ripster` block of the evidence document (BUILD_PROMPT, Justification).

    Keys: bias, stack, bars_since_stack_flip, c2_dir, c3_dir, c3_top, c3_bot, dir_w. Signs and
    the flip count are ints, the cloud edges floats; a null in the snapshot stays None (never 0).
    """
    block: dict[str, Any] = {}
    for key in _EVIDENCE_SIGNS:
        value = _opt(snapshot, f"ripster.{key}")
        block[key] = None if value is None else int(value)
    for key in _EVIDENCE_PRICES:
        block[key] = _opt(snapshot, f"ripster.{key}")
    return block
