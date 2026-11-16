# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Volume indicators (TS-IND-120, 121, 122, 130 and the extras TS-IND-230 to TS-IND-234).

Expected values come from plain-Python loops or hand arithmetic (derivations in comments).
"""

import math

import numpy as np
import pytest

from supertrends.indicators import volume as v

TOL = 1e-9


def _ref_ema(x: list[float], n: int) -> list[float]:
    """Plain-loop EMA: alpha 2/(n+1), seeded with the SMA of the first n values."""
    out = [math.nan] * len(x)
    alpha = 2.0 / (n + 1)
    prev = sum(x[:n]) / n
    out[n - 1] = prev
    for i in range(n, len(x)):
        prev = alpha * x[i] + (1 - alpha) * prev
        out[i] = prev
    return out


VOL = [100.0, 120.0, 90.0, 150.0, 110.0, 200.0, 130.0, 95.0, 170.0, 140.0, 160.0, 80.0, 220.0]


def test_ts_ind_120_volume_oscillator_matches_loop() -> None:
    """TS-IND-120: vo = 100 * (EMA5 - EMA10) / EMA10, computed with an independent loop."""
    e5 = _ref_ema(VOL, 5)
    e10 = _ref_ema(VOL, 10)
    got = v.volume_oscillator(np.array(VOL))
    assert np.isnan(got[:9]).all()
    for i in range(9, len(VOL)):
        assert got[i] == pytest.approx(100.0 * (e5[i] - e10[i]) / e10[i], abs=TOL)
    # Hand check at index 9: EMA5 = ?, EMA10 = SMA of first 10 = 1305 / 10 = 130.5.
    assert e10[9] == pytest.approx(130.5)


def test_ts_ind_121_relative_volume_is_volume_over_sma20() -> None:
    """TS-IND-121: relative volume = volume / SMA20(volume)."""
    vol = [float(100 + 10 * (i % 7)) for i in range(25)]
    got = v.relative_volume(np.array(vol))
    assert np.isnan(got[:19]).all()
    for t in range(19, 25):
        assert got[t] == pytest.approx(vol[t] / (sum(vol[t - 19 : t + 1]) / 20.0), abs=TOL)
    # Hand check: constant volume gives relative volume 1.
    assert v.relative_volume(np.full(20, 50.0))[19] == pytest.approx(1.0)


def test_ts_ind_122_cmf_matches_hand_values() -> None:
    """TS-IND-122: CMF(3) by hand, then CMF(20) against a plain loop."""
    high = np.array([10.0, 12.0, 11.0, 13.0])
    low = np.array([8.0, 10.0, 9.0, 11.0])
    close = np.array([9.5, 10.5, 9.0, 13.0])
    vol = np.array([100.0, 200.0, 300.0, 400.0])
    # mfm = ((c-l)-(h-c))/(h-l): bar0 (1.5-0.5)/2 = 0.5; bar1 (0.5-1.5)/2 = -0.5;
    # bar2 (0-2)/2 = -1; bar3 (2-0)/2 = 1.
    # mfv = 50, -100, -300, 400. CMF(3)[2] = -350/600, CMF(3)[3] = 0/900 = 0.
    got = v.cmf(high, low, close, vol, 3)
    assert np.isnan(got[:2]).all()
    assert got[2] == pytest.approx(-350.0 / 600.0, abs=TOL)
    assert got[3] == pytest.approx(0.0, abs=TOL)

    rng = np.random.default_rng(7)
    lo = 50 + rng.random(40)
    hi = lo + rng.random(40) + 0.1
    cl = lo + (hi - lo) * rng.random(40)
    vl = 1000 + rng.random(40) * 500
    got20 = v.cmf(hi, lo, cl, vl, 20)
    for t in range(19, 40):
        num = den = 0.0
        for k in range(t - 19, t + 1):
            num += ((cl[k] - lo[k]) - (hi[k] - cl[k])) / (hi[k] - lo[k]) * vl[k]
            den += vl[k]
        assert got20[t] == pytest.approx(num / den, abs=TOL)


def test_ts_ind_130_accumulation_distribution_days_counted_over_last_20() -> None:
    """TS-IND-130: up/down close with relative volume >= 1.5 over the last 20 sessions."""
    n = 60
    close = np.full(n, 100.0)
    vol = np.full(n, 100.0)
    # Bars 40..: spikes of volume 1000 (rel vol about 5 to 9, far above 1.5).
    # Bar 45 up close + spike (accumulation), bar 50 down close + spike (distribution),
    # bar 52 up close without spike (not counted), bar 55 up close + spike (accumulation).
    close[45:] = 101.0  # up at 45, flat after
    close[50:] = 100.0  # down at 50
    close[52:] = 101.0  # up at 52, no spike
    close[55:] = 102.0  # up at 55
    vol[[45, 50, 55]] = 1000.0
    got = v.accumulation_distribution_days(close, vol)
    assert np.isnan(got.accumulation[:38]).all()
    assert np.isnan(got.distribution[:38]).all()
    # Window of 20 ending at 59 covers bars 40..59: 45 (acc), 50 (dist), 55 (acc).
    assert got.accumulation[59] == 2.0
    assert got.distribution[59] == 1.0
    # Window ending at 50 covers 31..50: only 45 (acc) and 50 (dist).
    assert got.accumulation[50] == 1.0
    assert got.distribution[50] == 1.0
    # Window ending at 66 would drop bar 45; shorter series check at 59 with window 10 (50..59).
    short = v.accumulation_distribution_days(close, vol, window=10)
    assert short.accumulation[59] == 1.0
    assert short.distribution[59] == 1.0


def test_ts_ind_230_volume_oscillator_zero_ema_is_nan_and_rejects_bad_windows() -> None:
    """TS-IND-230: an all-zero volume gives NaN (not inf); invalid windows raise."""
    got = v.volume_oscillator(np.zeros(15))
    assert np.isnan(got).all()
    with pytest.raises(ValueError, match="window"):
        v.volume_oscillator(np.ones(15), short=0, long=5)


def test_ts_ind_231_obv_slope_sign_up_down_flat() -> None:
    """TS-IND-231: OBV slope sign over 20 bars is +1 rising, -1 falling, 0 flat."""
    n = 30
    vol = np.full(n, 100.0)
    up = v.obv_slope_sign(np.arange(n, dtype=np.float64), vol)
    down = v.obv_slope_sign(-np.arange(n, dtype=np.float64), vol)
    flat = v.obv_slope_sign(np.full(n, 5.0), vol)
    assert np.isnan(up[:19]).all()
    # OBV rises by 100 each bar when close rises: slope +100 per bar, sign +1.
    assert (up[19:] == 1.0).all()
    assert (down[19:] == -1.0).all()
    assert (flat[19:] == 0.0).all()


def test_ts_ind_232_cmf_zero_range_bar_contributes_zero_and_zero_volume_is_nan() -> None:
    """TS-IND-232: zero-range bar has multiplier 0; a zero volume sum gives NaN."""
    high = np.array([10.0, 10.0, 12.0])
    low = np.array([10.0, 10.0, 10.0])
    close = np.array([10.0, 10.0, 12.0])
    vol = np.array([100.0, 100.0, 100.0])
    got = v.cmf(high, low, close, vol, 3)
    # mfv = 0, 0, +100 (multiplier 1): CMF = 100 / 300.
    assert got[2] == pytest.approx(1.0 / 3.0)
    assert np.isnan(v.cmf(high, low, close, np.zeros(3), 3)[2])


def test_ts_ind_233_relative_volume_zero_average_is_nan() -> None:
    """TS-IND-233: an all-zero window has no average to divide by and gives NaN."""
    assert np.isnan(v.relative_volume(np.zeros(25))[19:]).all()


def test_ts_ind_234_length_mismatch_raises() -> None:
    """TS-IND-234: inputs of different lengths raise ValueError."""
    with pytest.raises(ValueError, match="length"):
        v.cmf(np.ones(5), np.ones(4), np.ones(5), np.ones(5), 3)
    with pytest.raises(ValueError, match="length"):
        v.obv_slope_sign(np.ones(5), np.ones(4))
