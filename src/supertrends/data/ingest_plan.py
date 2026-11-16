# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Pure planning helpers for ingestion (PRD FR-103 to FR-106, FR-115; ARCHITECTURE section 4).

No database or provider access: windows, regular-session filtering, new-split detection, and
the fundamentals refresh policy, so they are unit tested without Postgres.
"""

from collections.abc import Collection, Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from supertrends.data.calendar import session_bounds, sessions_between
from supertrends.data.providers.base import Bar, CorporateAction

NY = ZoneInfo("America/New_York")
BACKFILL_DAYS = 1130  # three years plus a margin of about a month
INTRADAY_BACKFILL_SESSIONS = 30
FIVE_MINUTES = timedelta(minutes=5)

Window = tuple[date, date]


def resolve_as_of(target: date | None, last_completed: date) -> date:
    """The session ingestion targets.

    `None` means the last completed session. An explicit date maps to the latest session on or
    before it (a weekend or holiday resolves to the prior session) and never to a later one
    than the last completed session.
    """
    if target is None:
        return last_completed
    sessions = sessions_between(target - timedelta(days=10), min(target, last_completed))
    if not sessions:
        msg = f"no XNYS session on or before {target.isoformat()}"
        raise ValueError(msg)
    return sessions[-1]


def daily_window(last_bar: date | None, as_of: date, *, full: bool = False) -> Window | None:
    """Daily fetch window, or None when there is nothing new to fetch.

    No stored bar (or `full`) means a backfill. Otherwise fetch from the day after the last
    stored bar; the window is skipped when no XNYS session lies in it, which covers weekends and
    holidays.
    """
    if full or last_bar is None:
        return as_of - timedelta(days=BACKFILL_DAYS), as_of
    start = last_bar + timedelta(days=1)
    if not sessions_between(start, as_of):
        return None
    return start, as_of


def intraday_window(last_ts: datetime | None, as_of: date) -> Window | None:
    """Five-minute fetch window, or None when the stored data already reaches `as_of`."""
    if last_ts is None:
        sessions = sessions_between(as_of - timedelta(days=60), as_of)
        return sessions[-INTRADAY_BACKFILL_SESSIONS], as_of
    last_day = last_ts.astimezone(NY).date()
    if last_day >= as_of:
        return None
    return last_day, as_of  # re-reads the last stored day: its tail may have been partial


def bar_date(bar: Bar) -> date:
    """Exchange date of a daily bar (naive timestamps are already exchange dates)."""
    ts = bar.ts
    return ts.date() if ts.tzinfo is None else ts.astimezone(NY).date()


def regular_session_only(bars: Iterable[Bar]) -> list[Bar]:
    """Keep 5-minute bars that start inside the regular session (early close on half days)."""
    bounds: dict[date, tuple[datetime, datetime]] = {}
    kept: list[Bar] = []
    for bar in bars:
        ts = bar.ts if bar.ts.tzinfo else bar.ts.replace(tzinfo=UTC)
        day = ts.astimezone(NY).date()
        if day not in bounds:
            if not sessions_between(day, day):
                continue
            bounds[day] = session_bounds(day)
        opens, closes = bounds[day]
        if opens <= ts < closes:
            kept.append(bar)
    return kept


def new_splits(
    known: Collection[tuple[date, str]], fetched: Sequence[CorporateAction]
) -> list[CorporateAction]:
    """Splits in `fetched` whose (ex_date, kind) is not already stored."""
    return [a for a in fetched if a.kind == "split" and (a.ex_date, a.kind) not in known]


def fundamentals_due(
    *,
    has_rows: bool,
    as_of: date,
    earnings_dates: Collection[date],
    full: bool = False,
) -> bool:
    """Refresh policy (FR-115): first load, weekly (first session of the ISO week), or the
    session after an earnings date."""
    if full or not has_rows:
        return True
    prior = sessions_between(as_of - timedelta(days=10), as_of - timedelta(days=1))
    previous = prior[-1] if prior else None
    first_of_week = previous is None or previous.isocalendar()[:2] != as_of.isocalendar()[:2]
    return first_of_week or (previous is not None and previous in earnings_dates)
