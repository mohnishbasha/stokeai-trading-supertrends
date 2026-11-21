# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Run states and the allowed edges (FR-901, ARCHITECTURE section 8.1, ADR-066).

The database trigger `supertrends_runs_guard` enforces the same edges; this module lets the
orchestrator refuse an illegal move before it reaches the database.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "PIPELINE",
    "TERMINAL",
    "ErrorCode",
    "IllegalTransitionError",
    "RunState",
    "can_transition",
    "check_transition",
]


class RunState(StrEnum):
    """The eight run states, in pipeline order, then the terminal failure state."""

    QUEUED = "queued"
    INGESTING = "ingesting"
    COMPUTING = "computing"
    SCORING = "scoring"
    SELECTING = "selecting"
    NARRATING = "narrating"
    PUBLISHED = "published"
    FAILED = "failed"


class ErrorCode(StrEnum):
    """`runs.error_code` values (ADR-021, ARCHITECTURE section 4.1)."""

    ABANDONED = "abandoned"
    NOT_PICKED_UP = "not_picked_up"
    BENCHMARK_UNAVAILABLE = "benchmark_unavailable"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INTERNAL = "internal"


PIPELINE: tuple[RunState, ...] = (
    RunState.QUEUED,
    RunState.INGESTING,
    RunState.COMPUTING,
    RunState.SCORING,
    RunState.SELECTING,
    RunState.NARRATING,
    RunState.PUBLISHED,
)
TERMINAL: frozenset[RunState] = frozenset({RunState.PUBLISHED, RunState.FAILED})


class IllegalTransitionError(ValueError):
    """A state change the state machine does not allow."""


def can_transition(src: RunState | None, dst: RunState) -> bool:
    """True when `src -> dst` is an edge. `None -> queued` is the insert of a new run.

    Edges: each pipeline state to the next, and any non-terminal state to `failed`.
    """
    if src is None:
        return dst == RunState.QUEUED
    if src in TERMINAL:
        return False
    if dst == RunState.FAILED:
        return True
    i = PIPELINE.index(src)
    return i + 1 < len(PIPELINE) and PIPELINE[i + 1] == dst


def check_transition(src: RunState | str | None, dst: RunState | str) -> RunState:
    """Validate the move and return `dst` as a RunState; raise IllegalTransitionError if not."""
    source = None if src is None else RunState(src)
    target = RunState(dst)
    if not can_transition(source, target):
        shown = "insert" if source is None else source.value
        msg = f"run state cannot move from {shown} to {target.value}"
        raise IllegalTransitionError(msg)
    return target
