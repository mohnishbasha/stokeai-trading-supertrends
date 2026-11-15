# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Data-quality classification (PRD FR-107, FR-108; ARCHITECTURE section 4).

Pure logic, no database. A ticker is, in precedence order:

- `insufficient_history`: fewer than `min_history_bars` daily bars (default 250, config key
  `min_history_bars`), or none at all;
- `stale`: the latest daily bar is older than the last completed session. The caller passes
  the last completed session from the XNYS calendar, so a holiday never makes a ticker stale;
- `degraded`: a run of more than `MAX_GAP_SESSIONS` consecutive missing sessions inside the
  scoring window (the last `GAP_WINDOW_SESSIONS` sessions up to the latest bar);
- `ok` otherwise.

The result is returned to the caller; the daily run stores it per run in
`ticker_scores.data_quality` (ARCHITECTURE section 5, ticker_scores).
"""

from collections.abc import Iterable
from datetime import date, timedelta
from typing import Literal

from supertrends.data.calendar import sessions_between

Quality = Literal["ok", "degraded", "stale", "insufficient_history"]

MIN_HISTORY_BARS = 250
MAX_GAP_SESSIONS = 3
GAP_WINDOW_SESSIONS = 252  # roughly one trading year
_CALENDAR_DAYS_PER_SESSION_WINDOW = 400  # generous calendar span covering the window


def longest_gap(bar_dates: Iterable[date], last_session: date, window: int) -> int:
    """Longest run of consecutive missing sessions between the window start and the latest bar."""
    present = sorted(set(bar_dates))
    if not present:
        return 0
    latest = min(present[-1], last_session)
    span = sessions_between(latest - timedelta(days=_CALENDAR_DAYS_PER_SESSION_WINDOW), latest)
    in_window = span[-window:]
    have = set(present)
    longest = run = 0
    for session in in_window:
        if session in have:
            run = 0
        else:
            run += 1
            longest = max(longest, run)
    return longest


def classify_quality(
    bar_dates: Iterable[date],
    last_session: date,
    *,
    min_history_bars: int = MIN_HISTORY_BARS,
    max_gap_sessions: int = MAX_GAP_SESSIONS,
    window: int = GAP_WINDOW_SESSIONS,
) -> Quality:
    """Classify one ticker from its stored daily bar dates and the last completed session."""
    dates = sorted(set(bar_dates))
    if len(dates) < min_history_bars:
        return "insufficient_history"
    if dates[-1] < last_session:
        return "stale"
    if longest_gap(dates, last_session, window) > max_gap_sessions:
        return "degraded"
    return "ok"
