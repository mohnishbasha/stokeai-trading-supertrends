# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Chart overlays and the Supertrend ribbon (S3-T09, FR-804)."""

from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from supertrends.runs.overlays import OhlcvSeries, compute_overlays, ribbon, weekly_series
from supertrends.scoring.config import load_scoring_config

CONFIG = load_scoring_config(Path(__file__).resolve().parents[3] / "config" / "scoring.yaml")


def _series(count: int = 260) -> OhlcvSeries:
    days: list[date] = []
    day = date(2025, 1, 6)
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    close = np.array([100 + i * 0.2 + 6 * math.sin(i / 5) for i in range(count)])
    return OhlcvSeries(days, close - 0.5, close + 1.5, close - 1.5, close, np.full(count, 1e6))


def test_overlays_have_all_keys_and_no_nan() -> None:
    out = compute_overlays(_series(), CONFIG)
    expected = {"supertrend", "ripster_c2", "ripster_c3", *(f"sma_{p}" for p in CONFIG.sma.periods)}
    assert set(out) == expected
    for points in out.values():
        assert points
        for p in points:
            assert all(not (isinstance(v, float) and math.isnan(v)) for v in p.values())
    assert {"value", "dir"} <= set(out["supertrend"][0])
    assert {"top", "bot", "dir"} <= set(out["ripster_c2"][0])


def test_sma_warmup_points_are_omitted() -> None:
    out = compute_overlays(_series(60), CONFIG)
    longest = max(CONFIG.sma.periods)
    assert longest > 60
    assert out[f"sma_{longest}"] == []
    assert len(out["sma_20"]) == 60 - 20 + 1


def test_weekly_series_labels_the_last_session_of_each_week() -> None:
    daily = _series(30)
    weekly = weekly_series(daily)
    assert len(weekly.dates) == 6
    assert all(d.weekday() <= 4 for d in weekly.dates)
    assert weekly.high[0] == max(daily.high[:5])


def test_ribbon_is_last_ten_directions_oldest_first() -> None:
    direction = np.array([np.nan, 1, 1, -1] + [1] * 7 + [-1], dtype=np.float64)
    assert ribbon(direction) == "UDUUUUUUUD"
    assert ribbon(np.array([np.nan, np.nan])) == ""
