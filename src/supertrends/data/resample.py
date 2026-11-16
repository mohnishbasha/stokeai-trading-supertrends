# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Weekly resampling of daily bars (PRD FR-102, ADR-033).

Weekly bars are computed in memory on demand; there is no weekly table. A week is the ISO
week (Monday to Sunday). The bar is labeled with the last session present in that week, which
is the Friday, or the Thursday when Friday is a holiday. A partial current week is included
only through the last bar supplied, so there is no look-ahead.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DailyRow:
    """One daily OHLCV row."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class WeeklyBar:
    """One weekly OHLCV bar; `week_ending` is the last session of the week in the input."""

    week_ending: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    sessions: int


def resample_weekly(rows: Iterable[DailyRow]) -> list[WeeklyBar]:
    """Resample daily rows (any order) to weekly bars, ascending by week ending date."""
    weeks: dict[tuple[int, int], list[DailyRow]] = {}
    for row in sorted(rows, key=lambda r: r.date):
        iso = row.date.isocalendar()
        weeks.setdefault((iso.year, iso.week), []).append(row)
    return [
        WeeklyBar(
            week_ending=group[-1].date,
            open=group[0].open,
            high=max(r.high for r in group),
            low=min(r.low for r in group),
            close=group[-1].close,
            volume=sum(r.volume for r in group),
            sessions=len(group),
        )
        for group in weeks.values()
    ]
