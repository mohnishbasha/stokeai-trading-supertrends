# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Run state machine, ULIDs and trade-date resolution (TS-OPS-002, 101 to 104; S3-T07)."""

from __future__ import annotations

import itertools
from datetime import UTC, date, datetime

import pytest

from supertrends.runs.dates import (
    DATE_IN_FUTURE,
    NOT_A_TRADING_DATE,
    SESSION_NOT_COMPLETE,
    TradeDateError,
    resolve_trade_date,
)
from supertrends.runs.ids import CROCKFORD, new_ulid
from supertrends.runs.state import (
    PIPELINE,
    IllegalTransitionError,
    RunState,
    can_transition,
    check_transition,
)

# Friday 2026-11-13 closes 21:00 UTC (16:00 New York, EST).
FRIDAY = date(2026, 11, 13)
AFTER_CLOSE = datetime(2026, 11, 13, 21, 45, tzinfo=UTC)


def test_unit_runs_state_machine_illegal_transition_raises() -> None:
    with pytest.raises(IllegalTransitionError, match="queued to computing"):
        check_transition(RunState.QUEUED, RunState.COMPUTING)
    with pytest.raises(IllegalTransitionError, match="scoring to computing"):
        check_transition("scoring", "computing")
    with pytest.raises(IllegalTransitionError, match="published to failed"):
        check_transition(RunState.PUBLISHED, RunState.FAILED)
    with pytest.raises(IllegalTransitionError, match="failed to queued"):
        check_transition(RunState.FAILED, RunState.QUEUED)
    with pytest.raises(IllegalTransitionError, match="insert to ingesting"):
        check_transition(None, RunState.INGESTING)
    with pytest.raises(ValueError, match="'nope'"):
        check_transition("queued", "nope")


def test_unit_runs_state_machine_allows_pipeline_edges_and_failure_from_any_active_state() -> None:
    assert check_transition(None, "queued") == RunState.QUEUED
    for src, dst in itertools.pairwise(PIPELINE):
        assert can_transition(src, dst)
    for state in PIPELINE[:-1]:
        assert can_transition(state, RunState.FAILED)
    assert not can_transition(RunState.NARRATING, RunState.NARRATING)
    assert not can_transition(RunState.PUBLISHED, RunState.PUBLISHED)
    edges = {(s, d) for s in (None, *RunState) for d in RunState if can_transition(s, d)}
    assert len(edges) == 1 + 6 + 6


def test_unit_runs_ulid_is_26_crockford_chars_and_time_ordered() -> None:
    a = new_ulid(datetime(2026, 11, 13, tzinfo=UTC), randomness=(1 << 80) - 1)
    b = new_ulid(datetime(2026, 11, 13, 0, 0, 0, 1000, tzinfo=UTC), randomness=0)
    assert len(a) == len(b) == 26
    assert set(a + b) <= set(CROCKFORD)
    assert a < b
    assert new_ulid() != new_ulid()
    with pytest.raises(ValueError, match="80-bit"):
        new_ulid(randomness=1 << 80)
    with pytest.raises(ValueError, match="out of ULID range"):
        new_ulid(datetime(1969, 12, 31, tzinfo=UTC))


def test_unit_runs_trade_date_default_is_today_after_close_plus_30_minutes() -> None:
    assert resolve_trade_date(None, AFTER_CLOSE) == FRIDAY
    with pytest.raises(TradeDateError) as early:
        resolve_trade_date(None, datetime(2026, 11, 13, 21, 15, tzinfo=UTC))
    assert early.value.code == SESSION_NOT_COMPLETE
    assert early.value.exit_code == 3
    # half day: Friday 2026-11-27 closes 13:00 New York (18:00 UTC)
    assert resolve_trade_date(None, datetime(2026, 11, 27, 18, 31, tzinfo=UTC)) == date(
        2026, 11, 27
    )


def test_unit_runs_trade_date_explicit_must_be_a_completed_session() -> None:
    assert resolve_trade_date(date(2026, 11, 12), AFTER_CLOSE) == date(2026, 11, 12)
    assert resolve_trade_date(FRIDAY, AFTER_CLOSE) == FRIDAY
    cases = {
        date(2026, 11, 14): DATE_IN_FUTURE,  # Saturday after now
        date(2026, 11, 8): NOT_A_TRADING_DATE,  # Sunday
        date(2026, 11, 26): DATE_IN_FUTURE,  # Thanksgiving, future
        date(2025, 12, 25): NOT_A_TRADING_DATE,  # Christmas
    }
    for day, code in cases.items():
        with pytest.raises(TradeDateError) as err:
            resolve_trade_date(day, AFTER_CLOSE)
        assert err.value.code == code, day
        assert err.value.exit_code == 2
    with pytest.raises(TradeDateError) as before_close:
        resolve_trade_date(FRIDAY, datetime(2026, 11, 13, 15, 0, tzinfo=UTC))
    assert before_close.value.code == DATE_IN_FUTURE


def test_unit_runs_trade_date_default_on_weekend_is_not_a_trading_date() -> None:
    with pytest.raises(TradeDateError) as err:
        resolve_trade_date(None, datetime(2026, 11, 14, 23, 0, tzinfo=UTC))
    assert err.value.code == NOT_A_TRADING_DATE
