# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Selection: candidate rules, ranking, correlation guard and the daily picks (FR-401 to FR-412).

`select` is the entry point the run orchestrator and the backtest call. Pure: no I/O, clock,
randomness or globals; it never reads LLM output.
"""

from supertrends.selection.candidates import (
    SIDES,
    CandidateCheck,
    Exclusion,
    SelectionInput,
    Side,
    SideCheck,
    buy_threshold,
    evaluate_candidate,
    rc_bias_gate,
    selection_input_from_snapshot,
    sell_threshold,
)
from supertrends.selection.correlation import (
    Duplicate,
    GuardResult,
    correlation_guard,
    pearson,
    return_correlation,
    simple_returns,
)
from supertrends.selection.ranking import (
    AlsoQualified,
    NearestMiss,
    Pick,
    PriorPicks,
    Selection,
    days_on_list,
    nearest_miss,
    rank_candidates,
    rank_key,
    select,
)

__all__ = [
    "SIDES",
    "AlsoQualified",
    "CandidateCheck",
    "Duplicate",
    "Exclusion",
    "GuardResult",
    "NearestMiss",
    "Pick",
    "PriorPicks",
    "Selection",
    "SelectionInput",
    "Side",
    "SideCheck",
    "buy_threshold",
    "correlation_guard",
    "days_on_list",
    "evaluate_candidate",
    "nearest_miss",
    "pearson",
    "rank_candidates",
    "rank_key",
    "rc_bias_gate",
    "return_correlation",
    "select",
    "selection_input_from_snapshot",
    "sell_threshold",
    "simple_returns",
]
