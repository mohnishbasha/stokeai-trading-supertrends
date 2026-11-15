# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Trend indicators (TS-IND-040 to TS-IND-044, TS-IND-060 to TS-IND-062).

Expected values come from plain-Python loops written in this file, never from the code under test.
"""

import math
from datetime import date

import numpy as np
import pytest
from numpy.typing import NDArray

from supertrends.data.providers.fixture import FixtureProvider, FixtureUniverse
from supertrends.indicators import trend as t

TOL = 1e-6
NAN = math.nan
FloatArray = NDArray[np.float64]


def arr(*values: float) -> FloatArray:
    return np.array(values, dtype=np.float64)


def fixture_ohlc(symbol: str = "FXA") -> tuple[FloatArray, FloatArray, FloatArray]:
    provider = FixtureProvider(FixtureUniverse(seed=20261114, end_date=date(2026, 11, 13)))
    bars = provider.daily_bars(symbol, date(2023, 1, 1), date(2026, 11, 13))
    return (
        np.array([b.high for b in bars]),
        np.array([b.low for b in bars]),
        np.array([b.close for b in bars]),
    )


def loop_sma(x: list[float], n: int) -> list[float]:
    return [NAN if i < n - 1 else sum(x[i - n + 1 : i + 1]) / n for i in range(len(x))]


def assert_close(actual: FloatArray, expected: list[float], tol: float = TOL) -> None:
    assert len(actual) == len(expected)
    for a, e in zip(actual.tolist(), expected, strict=True):
        if math.isnan(e):
            assert math.isnan(a)
        else:
            assert a == pytest.approx(e, abs=tol)


def test_ts_ind_040_sma_stack_matches_loops_on_synthetic_dataset() -> None:
    """TS-IND-040: SMA 20/50/200 on a fixture ticker match plain loops to 1e-6."""
    _, _, close = fixture_ohlc()
    values = close.tolist()
    stack = t.sma_stack(close)
    assert len(close) > 700
    assert_close(stack.sma20, loop_sma(values, 20))
    assert_close(stack.sma50, loop_sma(values, 50))
    assert_close(stack.sma200, loop_sma(values, 200))
    assert np.isnan(stack.sma200[198])
    assert not np.isnan(stack.sma200[199])


def test_ts_ind_041_sma_slope_sign_positive_negative_flat() -> None:
    """TS-IND-041: slope[t] = sma[t] - sma[t-5]; sign positive, negative, flat."""
    up = arr(*range(1, 21))  # SMA2 rises 1 per bar -> slope 5
    s_up = t.sma_slope(t.sma_stack(up, 2, 3, 4).sma20)
    assert np.isnan(s_up[:6]).all()  # sma defined from 1, slope from 1 + 5
    assert s_up[6] == pytest.approx(5.0)
    down = arr(*range(20, 0, -1))
    assert t.sma_slope(t.sma_stack(down, 2, 3, 4).sma20)[10] == pytest.approx(-5.0)
    flat = np.full(20, 7.0)
    assert t.sma_slope(t.sma_stack(flat, 2, 3, 4).sma20)[10] == 0.0
    # hand values with bars=2: [1,2,4,7,11,16,22] -> x[t]-x[t-2]
    assert_close(t.sma_slope(arr(1, 2, 4, 7, 11, 16, 22), 2), [NAN, NAN, 3, 5, 7, 9, 11])


def test_slope_default_and_invalid_bars() -> None:
    """TS-IND-041: default is 5 bars; bars < 1 is rejected."""
    x = arr(*[float(i * i) for i in range(10)])
    assert t.sma_slope(x)[5] == pytest.approx(25.0)
    with pytest.raises(ValueError, match="bars"):
        t.sma_slope(x, 0)


A_GOLD = arr(1, 1, 1, 2, 3, 3, 3)
B_FLAT = arr(2, 2, 2, 2, 2, 2, 2)


def test_ts_ind_042_golden_cross_reports_bar_index() -> None:
    """TS-IND-042: a crosses above b at index 4 (a[3]=2 <= b[3]=2, a[4]=3 > 2)."""
    ev = t.cross_events(A_GOLD, B_FLAT)
    assert ev.tolist() == [0, 0, 0, 0, 1, 0, 0]
    assert t.last_cross(A_GOLD, B_FLAT, 5) == t.Cross(4, 1)
    assert t.last_cross(A_GOLD, B_FLAT, 3) == t.Cross(4, 1)  # window = bars 4..6
    assert t.last_cross(A_GOLD, B_FLAT, 2) is None  # window = bars 5..6


def test_ts_ind_043_death_cross_reports_bar_index() -> None:
    """TS-IND-043: death cross at index 3 (a[2]=3 >= b[2]=3, a[3]=1 < 3); latest cross wins."""
    a = arr(4, 4, 3, 1, 1, 1, 5, 5)
    b = arr(3, 3, 3, 3, 3, 3, 3, 3)
    assert t.cross_events(a, b).tolist() == [0, 0, 0, -1, 0, 0, 1, 0]
    assert t.last_cross(a, b, 3) == t.Cross(6, 1)
    assert t.last_cross(a, b, 8) == t.Cross(6, 1)
    assert t.last_cross(a[:6], b[:6], 6) == t.Cross(3, -1)


def test_ts_ind_044_no_cross_returns_none() -> None:
    """TS-IND-044: no cross, NaN warm-up, short input, and a=b throughout report None."""
    assert t.last_cross(arr(5, 6, 7, 8), arr(1, 1, 1, 1), 4) is None
    assert t.last_cross(arr(NAN, NAN, 1, 2), arr(NAN, NAN, NAN, 1), 4) is None
    assert t.last_cross(arr(1), arr(1), 5) is None
    assert t.last_cross(arr(2, 2, 2), arr(2, 2, 2), 3) is None
    assert t.last_cross(arr(), arr(), 3) is None
    with pytest.raises(ValueError, match="lookback"):
        t.last_cross(arr(1, 2), arr(1, 2), 0)
    with pytest.raises(ValueError, match="same length"):
        t.cross_events(arr(1, 2), arr(1))


def test_cross_equality_handling() -> None:
    """TS-IND-042: equality counts as 'not above' on the prior bar, so touch-then-rise crosses."""
    assert t.cross_events(arr(1, 2, 3), arr(2, 2, 2)).tolist() == [0, 0, 1]
    assert t.cross_events(arr(3, 2, 1), arr(2, 2, 2)).tolist() == [0, 0, -1]
    # above, touch, then rise again: reported at the rise (documented literal reading)
    assert t.cross_events(arr(3, 2, 3), arr(2, 2, 2)).tolist() == [0, 0, 1]


def loop_adx(
    high: list[float], low: list[float], close: list[float], n: int
) -> tuple[list[float], list[float], list[float]]:
    """Classic Wilder: smoothed sums seeded with the first n sums, then s = s - s/n + x."""
    size = len(close)
    tr, pdm, mdm = [0.0] * size, [0.0] * size, [0.0] * size
    for i in range(1, size):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        up, dn = high[i] - high[i - 1], low[i - 1] - low[i]
        pdm[i] = up if (up > dn and up > 0) else 0.0
        mdm[i] = dn if (dn > up and dn > 0) else 0.0
    pdi, mdi, adx_ = [NAN] * size, [NAN] * size, [NAN] * size
    s_tr, s_p, s_m = sum(tr[1 : n + 1]), sum(pdm[1 : n + 1]), sum(mdm[1 : n + 1])
    dx = [NAN] * size
    for i in range(n, size):
        if i > n:
            s_tr += tr[i] - s_tr / n
            s_p += pdm[i] - s_p / n
            s_m += mdm[i] - s_m / n
        pdi[i] = 100 * s_p / s_tr if s_tr else 0.0
        mdi[i] = 100 * s_m / s_tr if s_tr else 0.0
        tot = pdi[i] + mdi[i]
        dx[i] = 100 * abs(pdi[i] - mdi[i]) / tot if tot else 0.0
    first = 2 * n - 1
    if size > first:
        prev = sum(dx[n : first + 1]) / n
        adx_[first] = prev
        for i in range(first + 1, size):
            prev = (prev * (n - 1) + dx[i]) / n
            adx_[i] = prev
    return pdi, mdi, adx_


def test_ts_ind_060_adx_matches_wilder_loop_hand_series_and_fixture() -> None:
    """TS-IND-060: ADX/+DI/-DI(14) match the classic Wilder sum formulation to 1e-6."""
    high = [10 + 0.3 * i + (1.5 if i % 4 == 0 else 0.4) for i in range(80)]
    low = [10 + 0.3 * i - (0.6 if i % 3 == 0 else 1.1) for i in range(80)]
    close = [
        (h + lo) / 2 + (0.2 if i % 2 else -0.2)
        for i, (h, lo) in enumerate(zip(high, low, strict=True))
    ]
    res = t.adx(np.array(high), np.array(low), np.array(close), 14)
    pdi, mdi, adx_ = loop_adx(high, low, close, 14)
    assert_close(res.plus_di, pdi)
    assert_close(res.minus_di, mdi)
    assert_close(res.adx, adx_)
    assert np.isnan(res.adx[26])
    assert not np.isnan(res.adx[27])
    assert np.isnan(res.plus_di[13])
    assert not np.isnan(res.plus_di[14])
    h, lo, c = fixture_ohlc("FXC")
    res2 = t.adx(h, lo, c)
    pdi, mdi, adx_ = loop_adx(h.tolist(), lo.tolist(), c.tolist(), 14)
    assert_close(res2.plus_di, pdi)
    assert_close(res2.minus_di, mdi)
    assert_close(res2.adx, adx_)


def test_ts_ind_061_adx_di_bounded_0_100() -> None:
    """TS-IND-061: DI and ADX are non-negative and bounded by 100; trend direction shows in DI."""
    for sym in ("FXA", "FXB", "FXD"):
        h, lo, c = fixture_ohlc(sym)
        res = t.adx(h, lo, c)
        for series in (res.adx, res.plus_di, res.minus_di):
            v = series[~np.isnan(series)]
            assert (v >= 0).all()
            assert (v <= 100).all()
    rising = arr(*[float(i) for i in range(1, 60)])
    res = t.adx(rising + 0.5, rising - 0.5, rising)
    assert res.plus_di[-1] > res.minus_di[-1]
    assert res.adx[-1] > 50


def test_ts_ind_062_adx_flat_series_returns_zero_without_division_error() -> None:
    """TS-IND-062: zero range input gives DI 0 and ADX 0, no warnings, warm-up NaN kept."""
    flat = np.full(60, 10.0)
    with np.errstate(all="raise"):
        res = t.adx(flat, flat, flat)
    assert np.isnan(res.adx[:27]).all()
    assert (res.adx[27:] == 0).all()
    assert (res.plus_di[14:] == 0).all()
    assert (res.minus_di[14:] == 0).all()


def test_adx_short_and_invalid_inputs() -> None:
    """TS-IND-060: short input is all NaN; mismatched lengths and n < 1 raise."""
    short = t.adx(arr(1, 2), arr(0, 1), arr(1, 1.5))
    assert np.isnan(short.adx).all()
    assert np.isnan(short.plus_di).all()
    assert len(t.adx(arr(), arr(), arr()).adx) == 0
    with pytest.raises(ValueError, match="same length"):
        t.adx(arr(1, 2), arr(1), arr(1, 2))
    with pytest.raises(ValueError, match="window"):
        t.adx(arr(1), arr(1), arr(1), 0)


def test_sma_stack_params_and_short_input() -> None:
    """TS-IND-040: custom windows work and input shorter than a window is all NaN."""
    stack = t.sma_stack(arr(1, 2, 3, 4), 2, 3, 5)
    assert_close(stack.sma20, [NAN, 1.5, 2.5, 3.5])
    assert_close(stack.sma50, [NAN, NAN, 2, 3])
    assert np.isnan(stack.sma200).all()


def test_slope_shorter_than_bars_is_all_nan() -> None:
    """TS-IND-041: fewer than bars+1 values gives all NaN."""
    assert np.isnan(t.sma_slope(arr(1, 2, 3), 5)).all()
