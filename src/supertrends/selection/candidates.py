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

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from supertrends.scoring.composite import ScoreCard
from supertrends.scoring.config import ScoringConfig

__all__ = [
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
    "evaluate_candidate",
    "rc_bias_gate",
    "selection_input_from_snapshot",
    "sell_threshold",
]

Side = Literal["buy", "sell"]
SIDES: tuple[Side, ...] = ("buy", "sell")

# Same wording as the S3-T14 helper `scoring.ripster_rules.selection_bias_gate`.
REASON_RC_BUY = "close below the 34/50 cloud"
REASON_RC_SELL = "close above the 34/50 cloud"
REASON_RC_UNAVAILABLE = "34/50 cloud bias not available"
REASON_STALE = "data quality is stale"
REASON_LIQUIDITY = "liquidity below the floor"


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
        raise NotImplementedError


def selection_input_from_snapshot(  # noqa: PLR0913 - keyword-only shifts mirror the record
    ticker: str,
    card: ScoreCard,
    snapshot: Mapping[str, Any],
    *,
    data_quality: str = "ok",
    buy_threshold_shift: float = 0.0,
    sell_threshold_shift: float = 0.0,
) -> SelectionInput:
    """Build a `SelectionInput` from the indicator snapshot paths selection reads."""
    raise NotImplementedError


def buy_threshold(entry: SelectionInput, config: ScoringConfig) -> float:
    """`thresholds.buy_display_min` plus the ticker's buy threshold shift."""
    raise NotImplementedError


def sell_threshold(entry: SelectionInput, config: ScoringConfig) -> float:
    """`thresholds.sell_display_max` minus the ticker's sell threshold shift."""
    raise NotImplementedError


def rc_bias_gate(rc_bias: int | None, side: Side, config: ScoringConfig) -> tuple[bool, str | None]:
    """The Ripster `rc_bias` selection gate (FR-334): `(passed, reason)`."""
    raise NotImplementedError


def evaluate_candidate(entry: SelectionInput, config: ScoringConfig) -> CandidateCheck:
    """Apply the buy and sell candidate rules to one ticker."""
    raise NotImplementedError
