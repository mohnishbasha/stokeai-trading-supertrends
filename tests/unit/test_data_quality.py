# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Data-quality classification and holiday handling (TS-ING-019 to 024)."""

from datetime import UTC, date, datetime

from supertrends.data.calendar import last_completed_session, sessions_between
from supertrends.data.quality import classify_quality, longest_gap

LAST = date(2026, 11, 13)


def _history(end: date, count: int) -> list[date]:
    days = sessions_between(date(2024, 1, 1), end)
    return days[-count:]


def test_unit_quality_full_history_latest_session_is_ok() -> None:
    assert classify_quality(_history(LAST, 300), LAST) == "ok"


def test_unit_quality_fewer_than_250_bars_marks_insufficient_history() -> None:
    assert classify_quality(_history(LAST, 249), LAST) == "insufficient_history"
    assert classify_quality([], LAST) == "insufficient_history"


def test_unit_quality_exactly_250_bars_is_scoreable() -> None:
    assert classify_quality(_history(LAST, 250), LAST) == "ok"


def test_unit_quality_latest_bar_older_than_last_session_marks_stale() -> None:
    bars = _history(date(2026, 11, 11), 300)  # two sessions old
    assert classify_quality(bars, LAST) == "stale"


def test_unit_quality_gap_more_than_3_sessions_marks_degraded() -> None:
    bars = _history(LAST, 300)
    missing = set(bars[-60:-56])  # a 4 session gap
    assert longest_gap(bars, LAST, 252) == 0
    kept = [d for d in bars if d not in missing]
    assert longest_gap(kept, LAST, 252) == 4
    assert classify_quality(kept, LAST) == "degraded"


def test_unit_quality_gap_of_exactly_3_sessions_is_ok() -> None:
    bars = _history(LAST, 300)
    kept = [d for d in bars if d not in set(bars[-60:-57])]
    assert classify_quality(kept, LAST) == "ok"


def test_unit_quality_gap_outside_scoring_window_ignored() -> None:
    bars = _history(LAST, 400)
    kept = [d for d in bars if d not in set(bars[10:16])]  # far older than 252 sessions
    assert classify_quality(kept, LAST) == "ok"


def test_unit_ingest_holiday_does_not_mark_tickers_stale() -> None:
    # Thanksgiving 2026-11-26: the last completed session is Wednesday, which every ticker has.
    now = datetime(2026, 11, 26, 15, tzinfo=UTC)
    last = last_completed_session(now)
    assert last == date(2026, 11, 25)
    assert classify_quality(_history(last, 300), last) == "ok"


def test_unit_ingest_half_day_session_treated_as_complete_session() -> None:
    # The day after Thanksgiving closes at 13:00 ET and counts as a session once closed.
    now = datetime(2026, 11, 27, 19, tzinfo=UTC)  # 14:00 ET
    last = last_completed_session(now)
    assert last == date(2026, 11, 27)
    assert classify_quality(_history(last, 300), last) == "ok"
    assert classify_quality(_history(date(2026, 11, 25), 300), last) == "stale"
