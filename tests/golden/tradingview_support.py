# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""TradingView export helpers (TEST_PLAN 5.4). Test-side only: nothing in src knows TradingView.

`tv_direction_to_internal` is the single conversion point for TradingView's sign convention
(negative means up). `load_export` parses a TradingView "Export chart data" CSV; see
`tests/golden/tradingview/README.md` for the accepted columns.
"""

import csv
import io
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def tv_direction_to_internal(tv_dir: float) -> float:
    """Convert TradingView `ta.supertrend` direction (negative = up) to ours (+1 up, -1 down)."""
    if math.isnan(tv_dir) or tv_dir == 0:
        msg = f"TradingView direction must be non-zero and not NaN, got {tv_dir}"
        raise ValueError(msg)
    return 1.0 if tv_dir < 0 else -1.0


@dataclass(frozen=True)
class TvExport:
    """A parsed export: OHLC plus the TradingView line and the direction in internal sign."""

    high: FloatArray
    low: FloatArray
    close: FloatArray
    line: FloatArray
    direction: FloatArray


def _num(text: str) -> float:
    text = text.strip()
    return math.nan if text == "" or text.lower() == "nan" else float(text)


def _column(header: dict[str, int], *names: str) -> int | None:
    for name in names:
        if name in header:
            return header[name]
    return None


def parse_export(text: str) -> TvExport:
    """Parse export CSV text.

    Required: `high`, `low`, `close` (any case). The Supertrend is read from either the plot
    pair `Up Trend` / `Down Trend` (one is NaN or empty on each bar; Up present means up) or a
    single `Supertrend` column together with a `Direction` column in TradingView's sign.
    """
    rows = list(csv.reader(io.StringIO(text)))
    header = {name.strip().lower(): i for i, name in enumerate(rows[0])}
    body = rows[1:]
    hi, lo, cl = (_column(header, k) for k in ("high", "low", "close"))
    if hi is None or lo is None or cl is None:
        msg = "export needs high, low and close columns"
        raise ValueError(msg)
    up = _column(header, "up trend", "supertrend up trend", "up")
    down = _column(header, "down trend", "supertrend down trend", "down")
    single = _column(header, "supertrend", "supertrend line")
    tv_dir = _column(header, "direction", "supertrend direction", "trend direction")
    line = np.full(len(body), np.nan)
    direction = np.full(len(body), np.nan)
    for i, row in enumerate(body):
        if up is not None and down is not None:
            u, d = _num(row[up]), _num(row[down])
            if not math.isnan(u) and not math.isnan(d):
                msg = f"row {i}: both Up Trend and Down Trend are set"
                raise ValueError(msg)
            if not math.isnan(u):
                line[i], direction[i] = u, 1.0
            elif not math.isnan(d):
                line[i], direction[i] = d, -1.0
        elif single is not None and tv_dir is not None:
            line[i] = _num(row[single])
            raw = _num(row[tv_dir])
            direction[i] = math.nan if math.isnan(raw) else tv_direction_to_internal(raw)
        else:
            msg = "export needs Up Trend and Down Trend columns, or Supertrend and Direction"
            raise ValueError(msg)
    return TvExport(
        high=np.array([_num(r[hi]) for r in body]),
        low=np.array([_num(r[lo]) for r in body]),
        close=np.array([_num(r[cl]) for r in body]),
        line=line,
        direction=direction,
    )


def load_export(path: Path) -> TvExport:
    return parse_export(path.read_text(encoding="utf-8-sig"))
