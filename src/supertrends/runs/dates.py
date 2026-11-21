# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Trade-date resolution for a daily run (ADR-022).

* No date: today in America/New_York. It must be a session that closed at least 30 minutes ago
  (half days use their early close), else `session_not_complete` (exit 3).
* An explicit date must be an XNYS session on or before the last completed session, else
  `not_a_trading_date` or `date_in_future` (exit 2).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from supertrends.data.calendar import is_session, last_completed_session, session_bounds

__all__ = [
    "CLOSE_GRACE",
    "DATE_IN_FUTURE",
    "NOT_A_TRADING_DATE",
    "SESSION_NOT_COMPLETE",
    "TradeDateError",
    "resolve_trade_date",
]

NEW_YORK = ZoneInfo("America/New_York")
CLOSE_GRACE = timedelta(minutes=30)
NOT_A_TRADING_DATE = "not_a_trading_date"
DATE_IN_FUTURE = "date_in_future"
SESSION_NOT_COMPLETE = "session_not_complete"
_EXIT_CODES = {NOT_A_TRADING_DATE: 2, DATE_IN_FUTURE: 2, SESSION_NOT_COMPLETE: 3}


class TradeDateError(ValueError):
    """The requested or default trade date cannot be run now. `exit_code` is the CLI code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = _EXIT_CODES[code]


def resolve_trade_date(requested: date | None, now: datetime | None = None) -> date:
    """The trade date to run for `requested` (None means today in New York) at `now` (UTC)."""
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    today = moment.astimezone(NEW_YORK).date()
    if requested is None:
        if not is_session(today):
            msg = f"{today.isoformat()} is not an XNYS session"
            raise TradeDateError(NOT_A_TRADING_DATE, msg)
        _, close = session_bounds(today)
        if moment < close + CLOSE_GRACE:
            msg = (
                f"session {today.isoformat()} is not complete until "
                f"{(close + CLOSE_GRACE).isoformat()}"
            )
            raise TradeDateError(SESSION_NOT_COMPLETE, msg)
        return today
    if requested > today:
        raise TradeDateError(DATE_IN_FUTURE, f"{requested.isoformat()} is in the future")
    if not is_session(requested):
        msg = f"{requested.isoformat()} is not an XNYS session"
        raise TradeDateError(NOT_A_TRADING_DATE, msg)
    if requested > last_completed_session(moment):
        msg = f"session {requested.isoformat()} has not closed yet"
        raise TradeDateError(DATE_IN_FUTURE, msg)
    return requested
