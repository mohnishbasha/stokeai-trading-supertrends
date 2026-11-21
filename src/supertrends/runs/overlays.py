# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Chart overlays and the Supertrend ribbon for the read API (FR-804, ARCHITECTURE 6.1 bars).

Pure functions over bar arrays: the Supertrend with direction, the configured SMAs and the
Ripster c2 and c3 clouds, aligned to the bars. Warm-up points (NaN) are omitted, so the output
is NaN-free JSON. The ribbon is the last 10 daily Supertrend directions, oldest first.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
from numpy.typing import NDArray

from supertrends.indicators.primitives import resample_weekly, sma
from supertrends.indicators.ripster_clouds import ripster_clouds
from supertrends.indicators.supertrend import supertrend
from supertrends.scoring.config import ScoringConfig

__all__ = ["RIBBON_LENGTH", "OhlcvSeries", "compute_overlays", "ribbon", "weekly_series"]

RIBBON_LENGTH = 10
C2, C3 = 1, 2  # indexes of the 5/12 and 34/50 clouds in `ripster_clouds`
FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class OhlcvSeries:
    """Aligned OHLCV arrays; `dates[i]` labels bar i."""

    dates: Sequence[date]
    open: FloatArray
    high: FloatArray
    low: FloatArray
    close: FloatArray
    volume: FloatArray


def weekly_series(daily: OhlcvSeries) -> OhlcvSeries:
    """Weekly bars of `daily` (ADR-033 semantics), labeled by the last session of the week."""
    arr_dates = np.array(list(daily.dates), dtype="datetime64[D]")
    weekly = resample_weekly(
        arr_dates, daily.open, daily.high, daily.low, daily.close, daily.volume
    )
    labels = [date.fromisoformat(str(d)) for d in weekly.week_ending]
    return OhlcvSeries(labels, weekly.open, weekly.high, weekly.low, weekly.close, weekly.volume)


def _finite(value: float) -> bool:
    return math.isfinite(float(value))


def _round(value: float) -> float:
    return round(float(value), 4)


def compute_overlays(series: OhlcvSeries, cfg: ScoringConfig) -> dict[str, list[dict[str, Any]]]:
    """Overlay series keyed `supertrend`, `sma_<period>`, `ripster_c2` and `ripster_c3`."""
    labels = [d.isoformat() for d in series.dates]
    st = supertrend(
        series.high, series.low, series.close, cfg.supertrend.atr_length, cfg.supertrend.factor
    )
    out: dict[str, list[dict[str, Any]]] = {
        "supertrend": [
            {"t": labels[i], "value": _round(st.line[i]), "dir": int(st.direction[i])}
            for i in range(len(labels))
            if _finite(st.line[i]) and _finite(st.direction[i])
        ]
    }
    for period in cfg.sma.periods:
        values = sma(series.close, period)
        out[f"sma_{period}"] = [
            {"t": labels[i], "value": _round(values[i])}
            for i in range(len(labels))
            if _finite(values[i])
        ]
    rc = cfg.ripster
    clouds = ripster_clouds(
        series.high,
        series.low,
        series.close,
        rc.clouds.pairs(),
        pullback_lookback=rc.pullback_lookback_bars,
    ).clouds
    for key, cloud in (("ripster_c2", clouds[C2]), ("ripster_c3", clouds[C3])):
        out[key] = [
            {
                "t": labels[i],
                "top": _round(cloud.top[i]),
                "bot": _round(cloud.bot[i]),
                "dir": int(cloud.direction[i]),
            }
            for i in range(len(labels))
            if _finite(cloud.top[i]) and _finite(cloud.bot[i]) and _finite(cloud.direction[i])
        ]
    return out


def ribbon(direction: FloatArray, length: int = RIBBON_LENGTH) -> str:
    """The last `length` Supertrend directions as `U` and `D`, oldest first."""
    tail = [d for d in direction[-length:] if _finite(d)]
    return "".join("U" if d > 0 else "D" for d in tail)
