# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Candidate rules (BUILD_PROMPT Signal Engine Specification, "Selection rules"; FR-401, FR-402,
FR-334, FR-412; S3-T06).

A ticker is a **buy candidate** when all hold, in this order: display >= 65 plus its threshold
shift, `st_dir_d == +1`, `rc_bias >= 0` (close not below the 34/50 cloud), confidence >= 50, data
quality not `stale`, average 20-day dollar volume >= 20,000,000. A **sell candidate** mirrors it:
display <= 35 minus its shift, `st_dir_d == -1`, `rc_bias <= 0`, and the same last three rules.
The 65, 35, 50 and 20,000,000 come from `thresholds.*` and `liquidity.*` in the scoring config.

Every failing rule is recorded as a reason, in rule order, so the first reason is the one shown
for a nearest miss (ADR-050). Pure: no I/O, clock or randomness.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from supertrends.scoring.composite import ScoreCard
from supertrends.scoring.config import ScoringConfig
from supertrends.scoring.factor import SELECTION_INPUT_PATHS, get_path
from supertrends.scoring.ripster_rules import (
    REJECT_BUY_REASON,
    REJECT_SELL_REASON,
    REJECT_UNAVAILABLE_REASON,
    selection_bias_gate,
)

__all__ = [
    "REASON_DIRECTION_UNAVAILABLE",
    "REASON_LIQUIDITY",
    "REASON_RC_BUY",
    "REASON_RC_SELL",
    "REASON_RC_UNAVAILABLE",
    "REASON_STALE",
    "SIDES",
    "CandidateCheck",
    "Exclusion",
    "SelectionInput",
    "Side",
    "SideCheck",
    "buy_threshold",
    "check_side",
    "evaluate_candidate",
    "rc_bias_gate",
    "selection_input_from_snapshot",
    "sell_threshold",
]

Side = Literal["buy", "sell"]
SIDES: tuple[Side, ...] = ("buy", "sell")

# The wording of the S3-T14 helper `scoring.ripster_rules.selection_bias_gate`.
REASON_RC_BUY = REJECT_BUY_REASON
REASON_RC_SELL = REJECT_SELL_REASON
REASON_RC_UNAVAILABLE = REJECT_UNAVAILABLE_REASON
REASON_STALE = "data quality is stale"
REASON_LIQUIDITY = "liquidity below the floor"
REASON_DIRECTION_UNAVAILABLE = "Supertrend direction not available"
STALE = "stale"

(_ST_DIR_PATH, _RC_BIAS_PATH, _ADV_PATH, _REL_VOL_PATH, _FLIP_PATH) = SELECTION_INPUT_PATHS


def check_side(side: str) -> Side:
    """Return `side` typed as a `Side`; ValueError for anything but "buy" or "sell"."""
    if side == "buy":
        return "buy"
    if side == "sell":
        return "sell"
    msg = f"side must be 'buy' or 'sell', got {side!r}"
    raise ValueError(msg)


def _fmt(value: float) -> str:
    """A threshold or confidence in a reason: up to two decimals, no trailing zeros (65, 49.96)."""
    return f"{round(value, 2):g}"


@dataclass(frozen=True)
class SelectionInput:
    """One scored ticker as selection sees it: the score card plus the snapshot values the rules
    and tie-breakers read (`scoring.factor.SELECTION_INPUT_PATHS`).

    * `st_dir_d` and `rc_bias` are -1, 0 or +1, or None while the indicator is warming up.
    * `bars_since_flip` and `relative_volume` are tie-breakers; None ranks last.
    * `data_quality` is the ingest quality (`ok`, `degraded`, `stale`, ...).
    * `buy_threshold_shift` raises the buy bar and `sell_threshold_shift` lowers the sell bar, in
      display points (>= 0). The fundamentals and market regime shifts are computed upstream
      (S5-T05); Sprint 3 runs pass 0.
    """

    ticker: str
    card: ScoreCard
    st_dir_d: int | None
    rc_bias: int | None
    bars_since_flip: int | None
    relative_volume: float | None
    avg_dollar_volume_20d: float | None
    data_quality: str = "ok"
    buy_threshold_shift: float = 0.0
    sell_threshold_shift: float = 0.0

    def __post_init__(self) -> None:
        if not self.ticker:
            msg = "ticker must not be empty"
            raise ValueError(msg)
        for name in ("buy_threshold_shift", "sell_threshold_shift"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                msg = f"{name} must be a finite number >= 0, got {value!r}"
                raise ValueError(msg)

    @property
    def display_score(self) -> float:
        return self.card.display_score

    @property
    def confidence(self) -> float:
        return self.card.confidence


@dataclass(frozen=True)
class Exclusion:
    """A ticker left out before scoring (`stale`, `insufficient_history`, ...); FR-412."""

    ticker: str
    reason: str


@dataclass(frozen=True)
class SideCheck:
    """The verdict of one side's rules: the adjusted threshold and every failing reason."""

    side: Side
    threshold: float
    reasons: tuple[str, ...]

    @property
    def qualified(self) -> bool:
        return not self.reasons


@dataclass(frozen=True)
class CandidateCheck:
    """Both sides' verdicts for one ticker."""

    ticker: str
    buy: SideCheck
    sell: SideCheck

    def side(self, side: Side) -> SideCheck:
        return self.buy if check_side(side) == "buy" else self.sell


def _optional(snapshot: Mapping[str, Any], path: str) -> float | None:
    value = get_path(snapshot, path)
    if value is None:
        return None
    number = float(value)
    return None if math.isnan(number) else number


def _optional_int(snapshot: Mapping[str, Any], path: str) -> int | None:
    value = _optional(snapshot, path)
    return None if value is None else int(value)


def selection_input_from_snapshot(  # noqa: PLR0913 - keyword-only shifts mirror the record
    ticker: str,
    card: ScoreCard,
    snapshot: Mapping[str, Any],
    *,
    data_quality: str = "ok",
    buy_threshold_shift: float = 0.0,
    sell_threshold_shift: float = 0.0,
) -> SelectionInput:
    """Build a `SelectionInput` from the indicator snapshot paths selection reads.

    Reads `scoring.factor.SELECTION_INPUT_PATHS`; a null or NaN value (warm-up) becomes None and
    an absent path raises KeyError naming it.
    """
    return SelectionInput(
        ticker=ticker,
        card=card,
        st_dir_d=_optional_int(snapshot, _ST_DIR_PATH),
        rc_bias=_optional_int(snapshot, _RC_BIAS_PATH),
        bars_since_flip=_optional_int(snapshot, _FLIP_PATH),
        relative_volume=_optional(snapshot, _REL_VOL_PATH),
        avg_dollar_volume_20d=_optional(snapshot, _ADV_PATH),
        data_quality=data_quality,
        buy_threshold_shift=buy_threshold_shift,
        sell_threshold_shift=sell_threshold_shift,
    )


def buy_threshold(entry: SelectionInput, config: ScoringConfig) -> float:
    """`thresholds.buy_display_min` plus the ticker's buy threshold shift."""
    return config.thresholds.buy_display_min + entry.buy_threshold_shift


def sell_threshold(entry: SelectionInput, config: ScoringConfig) -> float:
    """`thresholds.sell_display_max` minus the ticker's sell threshold shift."""
    return config.thresholds.sell_display_max - entry.sell_threshold_shift


def rc_bias_gate(rc_bias: int | None, side: Side, config: ScoringConfig) -> tuple[bool, str | None]:
    """The Ripster `rc_bias` selection gate (FR-334): `(passed, reason)`; reason None on a pass.

    A buy is rejected when the close is below the 34/50 cloud (`rc_bias < 0`), a sell when it is
    above (`rc_bias > 0`); inside the cloud (0) passes both. With `ripster.selection_bias_gate`
    false everything passes; an undefined bias fails closed. Raises ValueError for another side.

    Delegates to the S3-T14 helper `scoring.ripster_rules.selection_bias_gate`.
    """
    return selection_bias_gate({"ripster": {"bias": rc_bias}}, check_side(side), config)


def _side_check(entry: SelectionInput, side: Side, config: ScoringConfig) -> SideCheck:
    reasons: list[str] = []
    display = entry.display_score
    if side == "buy":
        threshold = buy_threshold(entry, config)
        if display < threshold:
            reasons.append(f"score below the buy threshold of {_fmt(threshold)}")
        want = 1
    else:
        threshold = sell_threshold(entry, config)
        if display > threshold:
            reasons.append(f"score above the sell threshold of {_fmt(threshold)}")
        want = -1
    if entry.st_dir_d is None:
        reasons.append(REASON_DIRECTION_UNAVAILABLE)
    elif entry.st_dir_d != want:
        reasons.append(f"Supertrend direction is {'down' if want == 1 else 'up'}")
    _, gate_reason = rc_bias_gate(entry.rc_bias, side, config)
    if gate_reason is not None:
        reasons.append(gate_reason)
    min_confidence = config.thresholds.min_confidence
    if entry.confidence < min_confidence:
        reasons.append(f"confidence {_fmt(entry.confidence)} below {_fmt(min_confidence)}")
    if entry.data_quality == STALE:
        reasons.append(REASON_STALE)
    floor = config.liquidity.min_avg_dollar_volume_20d
    if entry.avg_dollar_volume_20d is None or entry.avg_dollar_volume_20d < floor:
        reasons.append(REASON_LIQUIDITY)
    return SideCheck(side=side, threshold=threshold, reasons=tuple(reasons))


def evaluate_candidate(entry: SelectionInput, config: ScoringConfig) -> CandidateCheck:
    """Apply the buy and sell candidate rules to one ticker; reasons are in rule order."""
    return CandidateCheck(
        ticker=entry.ticker,
        buy=_side_check(entry, "buy", config),
        sell=_side_check(entry, "sell", config),
    )
