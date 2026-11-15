# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""XNYS calendar helpers (ADR-028)."""

from datetime import UTC, date, datetime

from supertrends.data.calendar import last_completed_session, session_bounds, sessions_between


def test_unit_calendar_sessions_skip_weekends_and_holidays() -> None:
    days = sessions_between(date(2026, 11, 23), date(2026, 11, 30))
    assert date(2026, 11, 26) not in days  # Thanksgiving
    assert date(2026, 11, 28) not in days
    assert days[0] == date(2026, 11, 23)
    assert sessions_between(date(2026, 11, 5), date(2026, 11, 1)) == []
    assert sessions_between(date(1990, 1, 1), date(1990, 1, 7)) == []


def test_unit_calendar_half_day_closes_early() -> None:
    o, c = session_bounds(date(2026, 11, 27))
    assert (c - o).total_seconds() == 3.5 * 3600
    o2, c2 = session_bounds(date(2026, 11, 13))
    assert (c2 - o2).total_seconds() == 6.5 * 3600


def test_unit_calendar_last_completed_session() -> None:
    assert last_completed_session(datetime(2026, 11, 15, 12, tzinfo=UTC)) == date(2026, 11, 13)
    # During the session on Friday the session is not yet complete.
    assert last_completed_session(datetime(2026, 11, 13, 15, tzinfo=UTC)) == date(2026, 11, 12)
    assert last_completed_session(datetime(2026, 11, 13, 21, 30, tzinfo=UTC)) == date(2026, 11, 13)
