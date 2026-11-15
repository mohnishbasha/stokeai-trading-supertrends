# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Compute budget for the indicator engine (TS-IND-094, NFR-001)."""

from __future__ import annotations

import time

from supertrends.indicators.registry import REGISTRY, compute_all
from tests.unit.indicators.lookahead_support import make_bundle

TICKERS = 200
SESSIONS = 756  # 3 years of daily bars
BUDGET_SECONDS = 60.0  # indicators plus scoring for 200 tickers on 2 cores; indicators alone here


def test_unit_perf_budget_200_tickers_3y_daily_compute_under_60s_on_2_cores() -> None:
    """TS-IND-094: every registered indicator for 200 tickers x 756 daily bars, single process."""
    bundles = [make_bundle(1000 + i, SESSIONS, intraday_from=SESSIONS - 30) for i in range(TICKERS)]
    start = time.perf_counter()
    for bundle in bundles:
        out = compute_all(bundle)
    elapsed = time.perf_counter() - start
    print(  # noqa: T201
        f"TS-IND-094 benchmark: {len(REGISTRY)} indicators, {TICKERS} tickers x {SESSIONS} bars, "
        f"{elapsed:.2f} s ({1000 * elapsed / TICKERS:.1f} ms per ticker)"
    )
    assert len(out) == len(REGISTRY)
    assert elapsed < BUDGET_SECONDS
