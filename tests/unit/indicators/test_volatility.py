# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Volatility indicator tests (TS-IND-083 to TS-IND-087, TS-IND-213 to TS-IND-217).

Expected values come from plain-Python loops written here, never from the code under test.
"""

import math

import numpy as np
import pytest
from numpy.typing import NDArray

from supertrends import indicators
from supertrends.indicators import volatility as v

TOL = 1e-6
NAN = math.nan


def series(count: int) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    close = [100.0 + 8.0 * math.sin(i / 11.0) + 0.05 * i + (i % 5) * 0.4 for i in range(count)]
    high = [c + 1.0 + (i % 3) * 0.3 for i, c in enumerate(close)]
    low = [c - 1.0 - (i % 4) * 0.2 for i, c in enumerate(close)]
    return (
        np.array(high, dtype=np.float64),
        np.array(low, dtype=np.float64),
        np.array(close, dtype=np.float64),
    )


def ref_bbw(close: list[float], n: int = 20) -> list[float]:
    out = [NAN] * len(close)
    for t in range(n - 1, len(close)):
        w = close[t - n + 1 : t + 1]
        mean = sum(w) / n
        sd = math.sqrt(sum((x - mean) ** 2 for x in w) / n)
        out[t] = 4 * sd / mean  # (upper - lower) / SMA = 2*k*sd / mean with k = 2
    return out


def ref_rank(x: list[float], n: int) -> list[float]:
    out = [NAN] * len(x)
    for t in range(n - 1, len(x)):
        w = x[t - n + 1 : t + 1]
        if any(math.isnan(e) for e in w):
            continue
        out[t] = 100.0 * sum(1 for e in w[:-1] if e < w[-1]) / (n - 1)
    return out


def ref_atr(high: list[float], low: list[float], close: list[float], n: int = 14) -> list[float]:
    tr = [high[0] - low[0]]
    for i in range(1, len(close)):
        tr.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
    out = [NAN] * len(close)
    out[n - 1] = sum(tr[:n]) / n
    for i in range(n, len(close)):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def assert_close(actual: NDArray[np.float64], expected: list[float]) -> None:
    assert len(actual) == len(expected)
    for a, e in zip(actual.tolist(), expected, strict=True):
        if math.isnan(e):
            assert math.isnan(a)
        else:
            assert abs(a - e) < TOL


def test_bandwidth_golden_1_to_20() -> None:
    """TS-IND-081 support: closes 1..20 give bandwidth 4*sqrt(33.25)/10.5 = 2.19668..."""
    bw = v.bandwidth(np.arange(1.0, 21.0))
    assert abs(bw[-1] - 4 * math.sqrt(33.25) / 10.5) < TOL
    assert np.isnan(bw[:19]).all()


def test_bbw_rank_126_bar_trailing_window() -> None:
    """TS-IND-084: bbw rank is the percentile within the trailing 126 bars (reference loop)."""
    _, _, close = series(300)
    rank = v.bbw_rank(close)
    assert_close(rank, ref_rank(ref_bbw(close.tolist()), 126))
    # Warm-up: bandwidth valid from index 19, rank valid from 19 + 125 = 144.
    assert np.isnan(rank[:144]).all()
    assert not np.isnan(rank[144])


def test_atr_pct_rank_252_bar_trailing_window() -> None:
    """TS-IND-083: ATR% = atr14/close and its rank over the trailing 252 bars (reference loop)."""
    high, low, close = series(400)
    atr = ref_atr(high.tolist(), low.tolist(), close.tolist())
    pct = [a / c for a, c in zip(atr, close.tolist(), strict=True)]
    assert_close(v.atr_pct(high, low, close), pct)
    rank = v.atr_pct_rank(high, low, close)
    assert_close(rank, ref_rank(pct, 252))
    assert np.isnan(rank[:264]).all()  # ATR% valid from 13, rank valid from 13 + 251 = 264
    assert not np.isnan(rank[264])


def test_rank_unchanged_when_future_bars_appended() -> None:
    """TS-IND-213: trailing-window outputs do not change when later bars are appended."""
    high, low, close = series(500)
    for cut in (300, 400):
        np.testing.assert_array_equal(v.bbw_rank(close[:cut]), v.bbw_rank(close)[:cut])
        np.testing.assert_array_equal(
            v.atr_pct_rank(high[:cut], low[:cut], close[:cut]),
            v.atr_pct_rank(high, low, close)[:cut],
        )
        np.testing.assert_array_equal(v.hv20(close[:cut]), v.hv20(close)[:cut])


def test_hv20_golden_log_returns_annualized() -> None:
    """TS-IND-085: HV20 = population stdev of 20 log returns * sqrt(252), within 1e-6.

    Hand case: closes alternating 100, 110 over 21 bars give 20 returns, 10 of +ln(1.1) and
    10 of -ln(1.1): mean 0, population stdev ln(1.1), so HV = ln(1.1) * sqrt(252).
    """
    close = [100.0 + 10.0 * (i % 2) for i in range(21)]
    out = v.hv20(np.array(close))
    assert abs(out[-1] - math.log(1.1) * math.sqrt(252)) < TOL
    assert np.isnan(out[:20]).all()

    _, _, longer = series(80)
    vals = longer.tolist()
    rets = [math.log(vals[i] / vals[i - 1]) for i in range(1, len(vals))]
    got = v.hv20(longer)
    for t in range(20, len(vals)):
        w = rets[t - 20 : t]
        m = sum(w) / 20
        assert abs(got[t] - math.sqrt(sum((x - m) ** 2 for x in w) / 20) * math.sqrt(252)) < TOL


def test_hv20_constant_series_zero_and_bad_close_nan() -> None:
    """TS-IND-214: constant closes give HV 0; a non-positive close gives NaN windows."""
    assert v.hv20(np.full(30, 10.0))[-1] == 0.0
    bad = np.full(30, 10.0)
    bad[5] = 0.0
    out = v.hv20(bad)
    assert np.isnan(out[5:26]).all()
    assert out[-1] == 0.0
    assert len(v.hv20(np.array([1.0]))) == 1


def test_squeeze_true_when_bbw_rank_below_15() -> None:
    """TS-IND-086: squeeze is strict: 14.99 true, 15.0 false, NaN stays NaN."""
    rank = np.array([NAN, 0.0, 14.99, 15.0, 15.01, 100.0])
    out = v.squeeze(rank)
    assert math.isnan(out[0])
    assert out[1:].tolist() == [1.0, 1.0, 0.0, 0.0, 0.0]


def test_expansion_requires_rank_above_85_and_bbw_rising_3_bars() -> None:
    """TS-IND-087: expansion needs rank > 85 and bbw rising 3 consecutive bars."""
    bbw = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 5.0, 6.0, 7.0, 6.0])
    rank = np.full(9, 90.0)
    out = v.expansion(rank, bbw)
    # t=3: 1<2<3<4 rising. t=4: 2<3<4<5 rising. t=5: 5 == 5 breaks. t=6,7: flat bar in window.
    # t=8: falls.
    assert out[3:].tolist() == [1.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    assert np.isnan(out[:3]).all()
    # Rank exactly 85 fails even when rising; 85.01 passes.
    assert v.expansion(np.full(9, 85.0), bbw)[3] == 0.0
    assert v.expansion(np.full(9, 85.01), bbw)[3] == 1.0


def test_expansion_nan_propagation_and_length_check() -> None:
    """TS-IND-215: NaN rank or NaN in the bbw window gives NaN; mismatched lengths raise."""
    bbw = np.array([NAN, 1.0, 2.0, 3.0, 4.0, 5.0])
    rank = np.array([NAN, NAN, 90.0, 90.0, NAN, 90.0])
    out = v.expansion(rank, bbw)
    assert np.isnan(out[:4]).all()  # t=3 window includes NaN bbw[0]
    assert math.isnan(out[4])  # rank NaN
    assert out[5] == 1.0
    assert len(v.expansion(np.array([1.0]), np.array([1.0]))) == 1
    with pytest.raises(ValueError, match="same length"):
        v.expansion(np.ones(3), np.ones(4))


def test_flat_prices_zero_bandwidth_and_zero_close() -> None:
    """TS-IND-216: flat closes give bandwidth 0 (not NaN); zero close gives NaN ATR%."""
    assert v.bandwidth(np.full(25, 50.0))[-1] == 0.0
    h = np.full(20, 1.0)
    assert np.isnan(v.atr_pct(h, h, np.zeros(20))).all()


def test_exports_aggregated() -> None:
    """TS-IND-217: volatility public names are in the module __all__ and the package aggregate."""
    names = ("atr_pct", "atr_pct_rank", "bandwidth", "bbw_rank", "expansion", "hv20", "squeeze")
    for name in names:
        assert name in v.__all__
        assert name in indicators.__all__
