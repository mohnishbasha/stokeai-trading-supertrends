# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Weekly resampling (TS-ING-025, TS-ING-026)."""

from datetime import date

from supertrends.data.resample import DailyRow, resample_weekly


def _row(day: date, o: float, h: float, low: float, c: float, v: int) -> DailyRow:  # noqa: PLR0917
    return DailyRow(day, o, h, low, c, v)


def test_unit_resample_weekly_week_ending_friday_ohlcv_correct() -> None:
    rows = [
        _row(date(2026, 11, 2), 10, 12, 9, 11, 100),
        _row(date(2026, 11, 3), 11, 15, 10, 14, 200),
        _row(date(2026, 11, 4), 14, 14, 8, 9, 300),
        _row(date(2026, 11, 5), 9, 10, 8.5, 9.5, 400),
        _row(date(2026, 11, 6), 9.5, 11, 9, 10.5, 500),
        _row(date(2026, 11, 9), 10.5, 13, 10, 12, 600),
    ]
    weeks = resample_weekly(reversed(rows))  # input order does not matter
    assert [w.week_ending for w in weeks] == [date(2026, 11, 6), date(2026, 11, 9)]
    first = weeks[0]
    assert (first.open, first.high, first.low, first.close) == (10, 15, 8, 10.5)
    assert (first.volume, first.sessions) == (1500, 5)
    partial = weeks[1]  # the current partial week is included only through the last bar
    assert (partial.open, partial.close, partial.volume, partial.sessions) == (10.5, 12, 600, 1)


def test_unit_resample_weekly_holiday_friday_uses_last_session_of_week() -> None:
    # Friday 2026-07-03 is the observed Independence Day holiday; the week ends Thursday.
    rows = [
        _row(date(2026, 6, 29), 1, 2, 1, 2, 10),
        _row(date(2026, 6, 30), 2, 3, 2, 3, 10),
        _row(date(2026, 7, 1), 3, 4, 3, 4, 10),
        _row(date(2026, 7, 2), 4, 5, 4, 5, 10),
    ]
    (week,) = resample_weekly(rows)
    assert week.week_ending == date(2026, 7, 2)
    assert week.close == 5


def test_unit_resample_weekly_empty_input_returns_empty_list() -> None:
    assert resample_weekly([]) == []
