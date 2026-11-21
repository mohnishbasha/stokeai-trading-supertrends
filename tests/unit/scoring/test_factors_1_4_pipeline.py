# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factors 1 to 4 on real snapshots: window boundaries against independent numpy (S3-T02).

The rule tables feed hand-built snapshots; these tests run `compute_snapshot` on a synthetic
bundle and compare the cross and run boundaries (10, 3 and 2/3 bars) with independent loops.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from supertrends.indicators.registry import Bundle
from supertrends.scoring.factor import FactorContext, FactorResult, Quality
from supertrends.scoring.factors import default_registry
from supertrends.scoring.snapshot import compute_snapshot
from tests.unit.indicators.lookahead_support import make_bundle
from tests.unit.scoring.factor_support import context, evidence_by_name, load_cfg

CFG = load_cfg()
CTX = context(CFG)
N = 700
FloatArray = NDArray[np.float64]


@pytest.fixture(scope="module")
def bundle() -> Bundle:
    return make_bundle(seed=8, n=N, sigma=0.02, intraday_from=None)


def _snapshot_at(bundle: Bundle, t: int) -> dict[str, Any]:
    return compute_snapshot(bundle, CFG, date.fromisoformat(str(bundle.dates[t])))


def _run(factor_id: str, snapshot: dict[str, Any]) -> FactorResult:
    return default_registry().get(factor_id).compute(snapshot, CTX)


def _sma(x: FloatArray, n: int) -> FloatArray:
    out = np.full(len(x), np.nan)
    for t in range(n - 1, len(x)):
        out[t] = x[t - n + 1 : t + 1].mean()
    return out


def _ema(x: FloatArray, n: int) -> FloatArray:
    """EMA with alpha 2 / (n + 1), seeded with the SMA of the first n values (spec Conventions)."""
    out = np.full(len(x), np.nan)
    out[n - 1] = x[:n].mean()
    for t in range(n, len(x)):
        out[t] = out[t - 1] + 2.0 / (n + 1) * (x[t] - out[t - 1])
    return out


def _macd(close: FloatArray) -> tuple[FloatArray, FloatArray, FloatArray]:
    line = _ema(close, 12) - _ema(close, 26)
    signal = np.full(len(close), np.nan)
    signal[25:] = _ema(line[25:], 9)
    return line, signal, line - signal


def _cross_bars(a: FloatArray, b: FloatArray) -> dict[int, int]:
    """Bar -> direction for each cross: previous a <= b and now a > b (+1), mirrored (-1)."""
    out: dict[int, int] = {}
    for t in range(1, len(a)):
        if np.isnan(a[t]) or np.isnan(a[t - 1]) or np.isnan(b[t]) or np.isnan(b[t - 1]):
            continue
        if a[t - 1] <= b[t - 1] and a[t] > b[t]:
            out[t] = 1
        elif a[t - 1] >= b[t - 1] and a[t] < b[t]:
            out[t] = -1
    return out


def _expected_cross(events: dict[int, int], t: int, window: int) -> int:
    """Direction of the latest cross among the last `window` bars ending at t, or 0."""
    hits = [bar for bar in events if t - window < bar <= t]
    return events[max(hits)] if hits else 0


def test_unit_sma_cross_boundary_10_bars_on_real_snapshots(bundle: Bundle) -> None:
    """TS-SCR-320: a SMA50/SMA200 cross counts through the 10th bar of the window, not the 11th."""
    close = bundle.close
    events = _cross_bars(_sma(close, 50), _sma(close, 200))
    assert len(events) >= 5  # the fixture must exercise the boundary
    inside = outside = 0
    for bar in events:
        for t in (bar, bar + 9, bar + 10):  # the cross bar, the 10th bar of the window, the 11th
            if t >= N:
                continue
            ev = evidence_by_name(_run("sma", _snapshot_at(bundle, t)))["sma_cross"]
            expected = _expected_cross(events, t, 10)  # last 10 bars: t-9..t
            assert ev[0] == expected, (bar, t)
            inside += expected != 0
            outside += expected == 0
    assert inside >= 5
    assert outside >= 1


def test_unit_macd_cross_boundary_3_bars_on_real_snapshots(bundle: Bundle) -> None:
    """TS-SCR-321: a MACD signal cross counts through the 3rd bar of the window, not the 4th."""
    line, signal, _ = _macd(bundle.close)
    events = _cross_bars(line, signal)
    assert len(events) >= 10
    inside = outside = 0
    for bar in list(events)[:25]:
        for t in (bar, bar + 2, bar + 3):  # the cross bar, the 3rd bar of the window, the 4th
            if t >= N:
                continue
            ev = evidence_by_name(_run("macd", _snapshot_at(bundle, t)))["macd_cross"]
            expected = _expected_cross(events, t, 3)  # last 3 bars: t-2..t
            assert ev[0] == expected, (bar, t)
            inside += expected != 0
            outside += expected == 0
    assert inside >= 10
    assert outside >= 1


def test_unit_macd_histogram_run_boundary_2_and_3_bars_on_real_snapshots(bundle: Bundle) -> None:
    """TS-SCR-322: histogram up 2 bars gives no run, 3 bars +1; down mirrors it with -1."""
    _, _, hist = _macd(bundle.close)
    diff = np.diff(hist, prepend=np.nan)
    seen: dict[tuple[int, int], int] = {}  # (sign, run length capped at 3) -> snapshots checked
    for t in range(40, N):
        for sign in (1, -1):
            k = 0
            while t - k >= 1 and sign * diff[t - k] > 0:
                k += 1
            key = (sign, min(k, 3))
            if k not in (2, 3) or seen.get(key, 0) >= 3:
                continue
            seen[key] = seen.get(key, 0) + 1
            ev = evidence_by_name(_run("macd", _snapshot_at(bundle, t)))["macd_hist_run"]
            assert ev[0] == (sign if k == 3 else 0), (t, sign, k)
    assert all(seen.get((s, k), 0) >= 1 for s in (1, -1) for k in (2, 3))


@pytest.mark.parametrize("t", [260, 400, 520, 699])
def test_unit_factors_1_to_4_on_real_snapshots_are_in_range_with_evidence(
    bundle: Bundle, t: int
) -> None:
    """TS-SCR-323: all four factors score a real snapshot: ok, in range, evidence, deterministic."""
    snapshot = _snapshot_at(bundle, t)
    for factor_id in ("supertrend", "sma", "macd", "divergence"):
        res = _run(factor_id, snapshot)
        assert res.quality is Quality.OK, factor_id
        assert -100.0 <= res.score <= 100.0
        assert res.evidence
        assert all(e.reason for e in res.evidence)
        assert _run(factor_id, snapshot) == res


def test_unit_factors_1_to_4_on_a_short_history_degrade_or_go_missing_not_raise() -> None:
    """TS-SCR-324: 40 bars: SMA200 is in warm-up (missing), weekly MACD is (degraded)."""
    short = make_bundle(seed=2, n=40, intraday_from=None)
    snapshot = compute_snapshot(short, CFG, date.fromisoformat(str(short.dates[-1])))
    ctx = FactorContext(config=CFG, as_of=date.fromisoformat(snapshot["as_of"]))
    sma = default_registry().get("sma").compute(snapshot, ctx)
    assert sma.quality is Quality.MISSING
    assert sma.score == 0
    macd = default_registry().get("macd").compute(snapshot, ctx)
    assert macd.quality is Quality.DEGRADED  # 40 bars is 8 weeks: no weekly MACD, daily MACD exists
    assert macd.score != 0
    for factor_id in ("supertrend", "divergence"):
        res = default_registry().get(factor_id).compute(snapshot, ctx)
        assert -100.0 <= res.score <= 100.0
