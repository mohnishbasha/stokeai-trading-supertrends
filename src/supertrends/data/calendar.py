# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""XNYS trading calendar helpers (ADR-028; reused by ingestion in S1-T06).

Thin wrapper over `exchange_calendars` so the rest of the code never imports the library
directly. Sessions are plain `date` values; session bounds are timezone-aware UTC datetimes
and include half days and holidays.
"""

from datetime import UTC, date, datetime, timedelta
from functools import lru_cache

import exchange_calendars as xcals


@lru_cache(maxsize=1)
def _xnys() -> xcals.ExchangeCalendar:
    return xcals.get_calendar("XNYS", start="2000-01-03", end=date.today() + timedelta(days=366))


def sessions_between(start: date, end: date) -> list[date]:
    """XNYS sessions in [start, end] inclusive, ascending."""
    if end < start:
        return []
    cal = _xnys()
    lo = max(start, cal.first_session.date())
    hi = min(end, cal.last_session.date())
    if hi < lo:
        return []
    return [ts.date() for ts in cal.sessions_in_range(lo.isoformat(), hi.isoformat())]


def last_completed_session(now: datetime | None = None) -> date:
    """The latest session whose close is at or before `now` (UTC, default the current time)."""
    moment = now or datetime.now(UTC)
    cal = _xnys()
    day = moment.astimezone(UTC).date()
    for session in reversed(sessions_between(day - timedelta(days=10), day)):
        if cal.session_close(session.isoformat()).to_pydatetime() <= moment:
            return session
    msg = f"no completed XNYS session found before {moment.isoformat()}"
    raise ValueError(msg)


def session_bounds(session: date) -> tuple[datetime, datetime]:
    """Regular-hours open and close of a session as aware UTC datetimes."""
    cal = _xnys()
    key = session.isoformat()
    return (
        cal.session_open(key).to_pydatetime().astimezone(UTC),
        cal.session_close(key).to_pydatetime().astimezone(UTC),
    )
