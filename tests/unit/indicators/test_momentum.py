# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""MACD indicators (TS-IND-050 to TS-IND-053).

Expected values come from plain-Python loops written in this file, never from the code under test.
"""

import math
from datetime import date, timedelta

import numpy as np
import pytest
from numpy.typing import NDArray

from supertrends.data.providers.fixture import FixtureProvider, FixtureUniverse
from supertrends.indicators import momentum as m
from supertrends.indicators.trend import Cross

TOL = 1e-6
NAN = math.nan
FloatArray = NDArray[np.float64]


def arr(*values: float) -> FloatArray:
    return np.array(values, dtype=np.float64)


def fixture_daily(symbol: str = "FXA") -> tuple[list[date], list[float]]:
    provider = FixtureProvider(FixtureUniverse(seed=20261114, end_date=date(2026, 11, 13)))
    bars = provider.daily_bars(symbol, date(2023, 1, 1), date(2026, 11, 13))
    return [b.ts.date() for b in bars], [b.close for b in bars]


def loop_ema(x: list[float], n: int) -> list[float]:
    """EMA alpha 2/(n+1) seeded with the SMA of the first n defined values."""
    out = [NAN] * len(x)
    defined = [i for i, v in enumerate(x) if not math.isnan(v)]
    if not defined or defined[0] + n > len(x):
        return out
    first = defined[0]
    seed = first + n - 1
    prev = sum(x[first : seed + 1]) / n
    out[seed] = prev
    for i in range(seed + 1, len(x)):
        prev = prev + 2.0 / (n + 1) * (x[i] - prev)
        out[i] = prev
    return out


def loop_macd(
    x: list[float], fast: int, slow: int, sig: int
) -> tuple[list[float], list[float], list[float]]:
    f, s = loop_ema(x, fast), loop_ema(x, slow)
    line = [a - b for a, b in zip(f, s, strict=True)]
    signal = loop_ema(line, sig)
    return line, signal, [a - b for a, b in zip(line, signal, strict=True)]


def assert_close(actual: FloatArray, expected: list[float], tol: float = TOL) -> None:
    assert len(actual) == len(expected)
    for i, (a, e) in enumerate(zip(actual.tolist(), expected, strict=True)):
        if math.isnan(e):
            assert math.isnan(a), i
        else:
            assert a == pytest.approx(e, abs=tol), i


def test_ts_ind_050_macd_daily_matches_loops_to_1e6() -> None:
    """TS-IND-050: line, signal, hist match plain-Python EMA loops on a fixture ticker."""
    _, close = fixture_daily()
    res = m.macd(np.array(close))
    line, signal, hist = loop_macd(close, 12, 26, 9)
    assert_close(res.line, line)
    assert_close(res.signal, signal)
    assert_close(res.hist, hist)
    assert np.isnan(res.line[24])
    assert not np.isnan(res.line[25])
    assert np.isnan(res.signal[32])
    assert not np.isnan(res.signal[33])


def test_ts_ind_050_macd_hand_values_and_params() -> None:
    """TS-IND-050: hand check with fast=2, slow=3, signal=2 on [1,2,4,7,11].

    EMA2 (alpha 2/3): seed idx1 = 1.5; idx2 = 1.5+2/3*(4-1.5) = 19/6; idx3 = 19/6+2/3*(7-19/6)=
    44/9... computed here by fractions-free arithmetic: the checks below use the same recurrences
    written out by hand.
    """
    x = [1.0, 2.0, 4.0, 7.0, 11.0]
    e2 = [NAN, 1.5, 1.5 + (2 / 3) * 2.5]
    e2.append(e2[2] + (2 / 3) * (7 - e2[2]))
    e2.append(e2[3] + (2 / 3) * (11 - e2[3]))
    e3 = [NAN, NAN, 7 / 3]  # SMA of 1,2,4
    e3.append(e3[2] + 0.5 * (7 - e3[2]))
    e3.append(e3[3] + 0.5 * (11 - e3[3]))
    line = [NAN, NAN, e2[2] - e3[2], e2[3] - e3[3], e2[4] - e3[4]]
    sig = [NAN, NAN, NAN, (line[2] + line[3]) / 2]
    sig.append(sig[3] + (2 / 3) * (line[4] - sig[3]))
    res = m.macd(np.array(x), 2, 3, 2)
    assert_close(res.line, line)
    assert_close(res.signal, sig)
    assert res.hist[4] == pytest.approx(line[4] - sig[4], abs=TOL)


def weekly_loop(
    dates: list[date], close: list[float]
) -> tuple[list[float], list[float], list[float]]:
    """As-of daily MACD from weekly closes: for each day, rebuild weekly closes up to that day."""
    n = len(close)
    line, signal, hist = [NAN] * n, [NAN] * n, [NAN] * n
    keys = [d.isocalendar()[:2] for d in dates]
    for t in range(n):
        weekly: list[float] = []
        for i in range(t + 1):
            if i == 0 or keys[i] != keys[i - 1]:
                weekly.append(close[i])
            else:
                weekly[-1] = close[i]
        ln, sg, hs = loop_macd(weekly, 12, 26, 9)
        line[t], signal[t], hist[t] = ln[-1], sg[-1], hs[-1]
    return line, signal, hist


def test_ts_ind_051_macd_weekly_matches_asof_loop_and_has_no_lookahead() -> None:
    """TS-IND-051: weekly MACD mapped to days equals a brute-force as-of recompute (1e-6)."""
    days, close = fixture_daily("FXC")
    res = m.macd_weekly(np.array(days, dtype="datetime64[D]"), np.array(close))
    line, signal, hist = weekly_loop(days, close)
    assert_close(res.line, line)
    assert_close(res.signal, signal)
    assert_close(res.hist, hist)
    assert not np.isnan(res.signal[-1])
    # no look-ahead: truncating the history leaves earlier values unchanged
    cut = 500
    part = m.macd_weekly(np.array(days[:cut], dtype="datetime64[D]"), np.array(close[:cut]))
    assert_close(part.hist, [float(v) for v in res.hist[:cut]], 1e-9)


def test_macd_weekly_small_params_and_short_input() -> None:
    """TS-IND-051: small periods exercise every seed path; too little history is NaN."""
    start = date(2024, 1, 1)  # a Monday
    days = [
        start + timedelta(days=i) for i in range(70) if (start + timedelta(days=i)).weekday() < 5
    ]
    close = [100 + math.sin(i / 3) * 5 + i * 0.1 for i in range(len(days))]
    res = m.macd_weekly(np.array(days, dtype="datetime64[D]"), np.array(close), 2, 3, 2)
    keys = [d.isocalendar()[:2] for d in days]
    for t in range(len(days)):
        weekly: list[float] = []
        for i in range(t + 1):
            if i == 0 or keys[i] != keys[i - 1]:
                weekly.append(close[i])
            else:
                weekly[-1] = close[i]
        ln, sg, hs = loop_macd(weekly, 2, 3, 2)
        for got, want in ((res.line[t], ln[-1]), (res.signal[t], sg[-1]), (res.hist[t], hs[-1])):
            if math.isnan(want):
                assert math.isnan(got), t
            else:
                assert got == pytest.approx(want, abs=TOL), t
    short = m.macd_weekly(np.array(days[:8], dtype="datetime64[D]"), np.array(close[:8]))
    assert np.isnan(short.line).all()
    empty = m.macd_weekly(np.array([], dtype="datetime64[D]"), arr())
    assert len(empty.line) == 0


def test_macd_invalid_params() -> None:
    """TS-IND-050: non-positive windows raise and fast >= slow is rejected."""
    with pytest.raises(ValueError, match="fast"):
        m.macd(arr(1, 2, 3), 5, 5, 2)
    with pytest.raises(ValueError, match="window"):
        m.macd(arr(1, 2, 3), 0, 5, 2)
    with pytest.raises(ValueError, match="fast"):
        m.macd_weekly(np.array([], dtype="datetime64[D]"), arr(), 5, 5, 2)


def test_ts_ind_052_signal_cross_bullish_and_bearish_within_3_bars() -> None:
    """TS-IND-052: bullish at idx 4 (line 0->1 over signal 0.5), bearish at idx 8."""
    line = arr(NAN, -1, -1, 0.0, 1.0, 1.5, 1.5, 1.0, -1.0, -1.0)
    sig = arr(NAN, 0.0, 0.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    # idx3: line 0.0 <= sig 0.5; idx4 line 1.0 > 0.5 -> bullish at 4
    # idx7: line 1.0 > 0.5 ; idx8: -1.0 < 0.5 -> bearish at 8
    assert m.macd_signal_cross(line, sig) == Cross(8, -1)
    assert m.macd_signal_cross(line[:7], sig[:7]) == Cross(4, 1)  # window bars 4..6
    assert m.macd_signal_cross(line[:8], sig[:8]) is None  # window bars 5..7, cross at 4 is old
    assert m.macd_signal_cross(line[:8], sig[:8], 4) == Cross(4, 1)
    assert m.macd_signal_cross(line, sig, 1) is None  # window is bar 9 only


def test_ts_ind_053_hist_run_three_rising_and_three_falling_bars() -> None:
    """TS-IND-053: +1 after 3 consecutive rises, -1 after 3 consecutive falls, else 0."""
    hist = arr(NAN, 1, 2, 3, 4, 4, 3, 2, 1, 2)
    # diffs: idx2 +, idx3 +, idx4 +, idx5 0, idx6 -, idx7 -, idx8 -, idx9 +
    out = m.hist_run(hist)
    assert out.tolist() == [0, 0, 0, 0, 1, 0, 0, 0, -1, 0]
    assert m.hist_run(hist, 2).tolist() == [0, 0, 0, 1, 1, 0, 0, -1, -1, 0]
    assert m.hist_run(arr(1, 2)).tolist() == [0, 0]
    assert len(m.hist_run(arr())) == 0
    with pytest.raises(ValueError, match="bars"):
        m.hist_run(hist, 0)
