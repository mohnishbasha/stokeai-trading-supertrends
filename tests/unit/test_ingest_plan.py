# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Incremental windows, session filtering, split detection, fundamentals policy."""

from datetime import UTC, date, datetime

import pytest

from supertrends.data.ingest_plan import (
    BACKFILL_DAYS,
    bar_date,
    daily_window,
    fundamentals_due,
    intraday_window,
    new_splits,
    regular_session_only,
    resolve_as_of,
)
from supertrends.data.providers.base import Bar, CorporateAction

AS_OF = date(2026, 11, 13)


def _bar(ts: datetime) -> Bar:
    return Bar("FXA", ts, 1.0, 2.0, 0.5, 1.5, 100)


def test_unit_ingest_daily_window_backfill_when_no_bars_or_full() -> None:
    window = daily_window(None, AS_OF)
    assert window is not None
    assert window[1] == AS_OF
    assert (AS_OF - window[0]).days == BACKFILL_DAYS
    assert daily_window(AS_OF, AS_OF, full=True) == daily_window(None, AS_OF)


def test_unit_ingest_incremental_fetch_starts_after_last_stored_bar() -> None:
    assert daily_window(date(2026, 11, 10), AS_OF) == (date(2026, 11, 11), AS_OF)
    assert daily_window(AS_OF, AS_OF) is None


def test_unit_ingest_window_skipped_when_only_weekend_or_holiday_follows() -> None:
    assert daily_window(date(2026, 11, 13), date(2026, 11, 15)) is None  # weekend
    assert daily_window(date(2026, 11, 25), date(2026, 11, 26)) is None  # Thanksgiving


def test_unit_ingest_intraday_window() -> None:
    first = intraday_window(None, AS_OF)
    assert first is not None
    assert first[1] == AS_OF
    last = datetime(2026, 11, 12, 20, 55, tzinfo=UTC)
    assert intraday_window(last, AS_OF) == (date(2026, 11, 12), AS_OF)
    assert intraday_window(datetime(2026, 11, 13, 20, 55, tzinfo=UTC), AS_OF) is None


def test_unit_ingest_resolve_as_of() -> None:
    assert resolve_as_of(None, AS_OF) == AS_OF
    assert resolve_as_of(date(2026, 11, 15), AS_OF) == AS_OF  # Sunday resolves to Friday
    assert resolve_as_of(date(2026, 11, 26), date(2026, 11, 27)) == date(2026, 11, 25)
    assert resolve_as_of(date(2026, 11, 20), AS_OF) == AS_OF  # never beyond last completed
    with pytest.raises(ValueError, match="no XNYS session"):
        resolve_as_of(date(1990, 1, 1), AS_OF)


def test_unit_ingest_bar_date_handles_naive_and_aware_timestamps() -> None:
    assert bar_date(_bar(datetime(2026, 11, 13))) == AS_OF
    assert bar_date(_bar(datetime(2026, 11, 13, 5, tzinfo=UTC))) == AS_OF


def test_unit_ingest_regular_session_only_drops_pre_and_after_hours() -> None:
    pre = _bar(datetime(2026, 11, 13, 13, 0, tzinfo=UTC))  # 08:00 ET
    first = _bar(datetime(2026, 11, 13, 14, 30, tzinfo=UTC))  # 09:30 ET
    last = _bar(datetime(2026, 11, 13, 20, 55, tzinfo=UTC))  # 15:55 ET
    after = _bar(datetime(2026, 11, 13, 21, 0, tzinfo=UTC))  # 16:00 ET
    weekend = _bar(datetime(2026, 11, 14, 15, 0, tzinfo=UTC))
    assert regular_session_only([pre, first, last, after, weekend]) == [first, last]


def test_unit_ingest_regular_session_only_half_day_cuts_at_early_close() -> None:
    inside = _bar(datetime(2026, 11, 27, 17, 55, tzinfo=UTC))  # 12:55 ET
    outside = _bar(datetime(2026, 11, 27, 18, 0, tzinfo=UTC))  # 13:00 ET close
    assert regular_session_only([inside, outside]) == [inside]


def test_unit_ingest_new_splits_ignores_known_and_dividends() -> None:
    known = {(date(2025, 3, 3), "split")}
    fetched = [
        CorporateAction("FXE", date(2025, 3, 3), "split", 4.0, None),
        CorporateAction("FXE", date(2026, 11, 12), "split", 2.0, None),
        CorporateAction("FXE", date(2026, 11, 12), "dividend", None, 0.5),
    ]
    assert new_splits(known, fetched) == [fetched[1]]


def test_unit_ingest_fundamentals_due_policy() -> None:
    wed = date(2026, 11, 11)
    mon = date(2026, 11, 9)
    assert fundamentals_due(has_rows=False, as_of=wed, earnings_dates=set())
    assert not fundamentals_due(has_rows=True, as_of=wed, earnings_dates=set())
    assert fundamentals_due(has_rows=True, as_of=wed, earnings_dates=set(), full=True)
    assert fundamentals_due(has_rows=True, as_of=mon, earnings_dates=set())  # weekly
    assert fundamentals_due(has_rows=True, as_of=wed, earnings_dates={date(2026, 11, 10)})
    assert not fundamentals_due(has_rows=True, as_of=wed, earnings_dates={date(2026, 11, 3)})
