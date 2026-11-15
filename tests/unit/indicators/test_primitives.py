# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Indicator primitives (TS-IND-001 to TS-IND-016 plus the aggregation checks, TS-IND-017/018).

Expected values are derived independently of the code under test: either by hand (the
derivation is in a comment) or by a plain-Python loop written in this file.
"""

import importlib
import math
from datetime import date

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from supertrends import indicators
from supertrends.data.providers.fixture import FixtureProvider, FixtureUniverse
from supertrends.data.resample import DailyRow
from supertrends.data.resample import resample_weekly as data_resample_weekly
from supertrends.indicators import primitives as p

TOL = 1e-9
NAN = math.nan


def arr(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


def assert_close(actual: NDArray[np.float64], expected: list[float]) -> None:
    """Equal length, NaN in the same places, finite values within 1e-9."""
    assert len(actual) == len(expected)
    for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
        if math.isnan(e):
            assert math.isnan(a), f"index {i}: expected NaN, got {a}"
        else:
            assert abs(a - e) <= TOL, f"index {i}: {a} != {e}"


SERIES = arr(1, 3, 2, 5, 4, 6, 8, 7)


def _wave(n: int) -> list[float]:
    """Deterministic non-trivial price-like series, no numpy in the generator."""
    return [100.0 + 10.0 * math.sin(i / 3.0) + 0.5 * ((i * 7) % 5) for i in range(n)]


def test_golden_sma_compute_handcomputed_series_matches_1e9() -> None:
    """TS-IND-001: SMA(5) on a hand series.

    Windows of [1,3,2,5,4,6,8,7]: (1+3+2+5+4)/5=3, (3+2+5+4+6)/5=4, (2+5+4+6+8)/5=5,
    (5+4+6+8+7)/5=6. The first n-1 = 4 bars are NaN.
    """
    assert_close(p.sma(SERIES, 5), [NAN, NAN, NAN, NAN, 3, 4, 5, 6])


def test_golden_ema_compute_seeded_with_sma_of_first_n_matches_1e9() -> None:
    """TS-IND-002: EMA(3), alpha 0.5, seeded at index 2 with SMA(1,3,2) = 2.

    i3: .5*5+.5*2 = 3.5; i4: .5*4+.5*3.5 = 3.75; i5: .5*6+.5*3.75 = 4.875;
    i6: .5*8+.5*4.875 = 6.4375; i7: .5*7+.5*6.4375 = 6.71875.
    """
    assert_close(p.ema(SERIES, 3), [NAN, NAN, 2, 3.5, 3.75, 4.875, 6.4375, 6.71875])


def test_golden_rma_compute_wilder_seed_and_recursion_matches_1e9() -> None:
    """TS-IND-003: RMA(3) seeded with SMA(1,3,2)=2, then (prev*2+x)/3.

    i3: (4+5)/3 = 3; i4: (6+4)/3 = 10/3; i5: (20/3+6)/3 = 38/9; i6: (76/9+8)/3 = 148/27;
    i7: (296/27+7)/3 = 485/81.
    """
    assert_close(p.rma(SERIES, 3), [NAN, NAN, 2, 3, 10 / 3, 38 / 9, 148 / 27, 485 / 81])


def test_unit_ema_rma_leading_nan_skipped_and_mid_series_nan_propagates() -> None:
    """TS-IND-002/003 (NaN policy): leading NaN delays the seed, a later NaN poisons the rest."""
    lead = arr(NAN, NAN, 1, 3, 2, 5)
    assert_close(p.ema(lead, 3), [NAN, NAN, NAN, NAN, 2, 3.5])
    assert_close(p.rma(lead, 3), [NAN, NAN, NAN, NAN, 2, 3])
    mid = arr(1, 3, 2, NAN, 4, 6)
    assert_close(p.ema(mid, 3), [NAN, NAN, 2, NAN, NAN, NAN])
    assert_close(p.rma(mid, 3), [NAN, NAN, 2, NAN, NAN, NAN])
    assert_close(p.sma(mid, 3), [NAN, NAN, 2, NAN, NAN, NAN])
    assert_close(p.ema(arr(1, 2), 5), [NAN, NAN])


def test_golden_true_range_compute_gap_up_gap_down_inside_bar_matches_1e9() -> None:
    """TS-IND-004: TR = max(h-l, |h-prev close|, |l-prev close|).

    Bars (h,l,c): (10,8,9), (12,9,11), (15,13,14), (10,7,8), (9,8,8.5).
    i1 normal: max(3, 3, 0) = 3; i2 gap up: max(2, |15-11|=4, |13-11|=2) = 4;
    i3 gap down: max(3, |10-14|=4, |7-14|=7) = 7; i4 inside: max(1, |9-8|=1, 0) = 1.
    """
    high = arr(10, 12, 15, 10, 9)
    low = arr(8, 9, 13, 7, 8)
    close = arr(9, 11, 14, 8, 8.5)
    assert_close(p.true_range(high, low, close), [2, 3, 4, 7, 1])


def test_unit_true_range_compute_first_bar_is_high_minus_low() -> None:
    """TS-IND-005: the first bar has no prior close, so TR is high - low."""
    tr = p.true_range(arr(11.5, 12), arr(10, 11), arr(11, 11.5))
    assert tr[0] == pytest.approx(1.5, abs=TOL)


def _ref_rma(values: list[float], n: int) -> list[float]:
    out = [NAN] * len(values)
    avg = sum(values[:n]) / n
    out[n - 1] = avg
    for i in range(n, len(values)):
        avg = (avg * (n - 1) + values[i]) / n
        out[i] = avg
    return out


def _ref_tr(high: list[float], low: list[float], close: list[float]) -> list[float]:
    out = [high[0] - low[0]]
    for i in range(1, len(high)):
        out.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
    return out


def test_golden_atr_compute_rma10_and_rma14_match_1e9() -> None:
    """TS-IND-006: ATR is the RMA of TR; hand case plus a 60-bar plain-Python reference.

    Hand case: TR [2,3,4,7,1], ATR(2): seed (2+3)/2 = 2.5; (2.5+4)/2 = 3.25;
    (3.25+7)/2 = 5.125; (5.125+1)/2 = 3.0625.
    """
    high = arr(10, 12, 15, 10, 9)
    low = arr(8, 9, 13, 7, 8)
    close = arr(9, 11, 14, 8, 8.5)
    assert_close(p.atr(high, low, close, 2), [NAN, 2.5, 3.25, 5.125, 3.0625])

    closes = _wave(60)
    highs = [c + 1.0 + (i % 4) * 0.3 for i, c in enumerate(closes)]
    lows = [c - 1.0 - (i % 3) * 0.4 for i, c in enumerate(closes)]
    tr = _ref_tr(highs, lows, closes)
    for n in (10, 14):
        got = p.atr(np.array(highs), np.array(lows), np.array(closes), n)
        assert_close(got, _ref_rma(tr, n))
    default = p.atr(np.array(highs), np.array(lows), np.array(closes))
    assert_close(default, _ref_rma(tr, 14))


def _ref_rsi(close: list[float], n: int) -> list[float]:
    out = [NAN] * len(close)
    gains = [max(close[i] - close[i - 1], 0.0) for i in range(1, len(close))]
    losses = [max(close[i - 1] - close[i], 0.0) for i in range(1, len(close))]
    ag = sum(gains[:n]) / n
    al = sum(losses[:n]) / n
    out[n] = 100.0 - 100.0 / (1.0 + ag / al)
    for i in range(n, len(gains)):
        ag = (ag * (n - 1) + gains[i]) / n
        al = (al * (n - 1) + losses[i]) / n
        out[i + 1] = 100.0 - 100.0 / (1.0 + ag / al)
    return out


def test_golden_rsi_compute_wilder_14_matches_1e9() -> None:
    """TS-IND-007: Wilder RSI(14) on a deterministic series; first value at index 14."""
    closes = _wave(80)
    expected = _ref_rsi(closes, 14)
    assert_close(p.rsi(np.array(closes)), expected)
    assert math.isnan(expected[13])
    assert not math.isnan(expected[14])
    # Hand case: n=2 on [1,2,1,2]: changes +1,-1,+1; seed ag=.5, al=.5 -> RSI 50 at index 2;
    # index 3: ag=(.5+1)/2=.75, al=(.5+0)/2=.25 -> RS 3 -> 75.
    assert_close(p.rsi(arr(1, 2, 1, 2), 2), [NAN, NAN, 50, 75])


def test_unit_rsi_compute_all_gains_returns_100_all_losses_returns_0() -> None:
    """TS-IND-008: degenerate series; a flat window (no gains, no losses) is defined as 50."""
    up = p.rsi(np.arange(1.0, 30.0), 14)
    down = p.rsi(np.arange(30.0, 1.0, -1.0), 14)
    flat = p.rsi(np.full(30, 7.0), 14)
    assert np.isnan(up[:14]).all()
    assert np.isnan(down[:14]).all()
    assert np.isnan(flat[:14]).all()
    assert (up[14:] == 100.0).all()
    assert (down[14:] == 0.0).all()
    assert (flat[14:] == 50.0).all()


def test_golden_obv_compute_up_down_flat_closes_matches_1e9() -> None:
    """TS-IND-009: closes 10,11,11,10,12 with volumes 100..500.

    obv0 = 0; up +200 -> 200; flat -> 200; down -400 -> -200; up +500 -> 300.
    """
    got = p.obv(arr(10, 11, 11, 10, 12), arr(100, 200, 300, 400, 500))
    assert_close(got, [0, 200, 200, -200, 300])


def test_golden_stdev_compute_population_20_matches_1e9() -> None:
    """TS-IND-010: population stdev (ddof=0).

    Hand case: [2,4,4,4,5,5,7,9] has mean 5, squared deviations sum 32, so sd = sqrt(32/8) = 2
    (the sample stdev would be 2.138...). Plus a 20-bar plain-Python reference.
    """
    assert_close(p.stdev(arr(2, 4, 4, 4, 5, 5, 7, 9), 8), [NAN] * 7 + [2.0])
    closes = _wave(50)
    expected = [NAN] * 19
    for i in range(19, 50):
        w = closes[i - 19 : i + 1]
        m = sum(w) / 20
        expected.append(math.sqrt(sum((v - m) ** 2 for v in w) / 20))
    assert_close(p.stdev(np.array(closes), 20), expected)


def test_unit_percentile_rank_compute_trailing_window_only_matches_1e9() -> None:
    """TS-IND-011: share of the previous n-1 values in the window strictly below the current, x100.

    x=[3,1,4,1,5,9,2,6], n=4. i3 [3,1,4|1]: 0 below of 3 -> 0; i4 [1,4,1|5]: 3/3 -> 100;
    i5 [4,1,5|9]: 3/3 -> 100; i6 [1,5,9|2]: 1/3 -> 33.33..; i7 [5,9,2|6]: 2/3 -> 66.67...
    """
    x = arr(3, 1, 4, 1, 5, 9, 2, 6)
    expected = [NAN, NAN, NAN, 0, 100, 100, 100 / 3, 200 / 3]
    assert_close(p.percentile_rank(x, 4), expected)
    # Trailing only: changing bars after t never changes the value at t.
    changed = x.copy()
    changed[6:] = [100, -100]
    assert_close(p.percentile_rank(changed, 4)[:6], expected[:6])
    # Ties are not "below": a constant series ranks 0.
    assert_close(p.percentile_rank(arr(5, 5, 5, 5), 3), [NAN, NAN, 0, 0])
    # A NaN anywhere in the window gives NaN; [1,3|4] is 2/2 below.
    assert_close(p.percentile_rank(arr(NAN, 1, 3, 4), 3), [NAN, NAN, NAN, 100])
    assert_close(p.percentile_rank(arr(1, NAN, 3, 4), 3), [NAN, NAN, NAN, NAN])


def test_golden_linreg_slope_compute_known_line_returns_exact_slope() -> None:
    """TS-IND-012: slope of y=2x+1 is 2 in every window; hand case [1,2,4,3] with n=3.

    x=0,1,2 centered -1,0,1: [1,2,4] -> (-1+4)/2 = 1.5; [2,4,3] -> (-2+3)/2 = 0.5.
    """
    line = 2.0 * np.arange(10.0) + 1.0
    assert_close(p.linreg_slope(line, 5), [NAN] * 4 + [2.0] * 6)
    assert_close(p.linreg_slope(arr(1, 2, 4, 3), 3), [NAN, NAN, 1.5, 0.5])


def test_unit_pivots_compute_width_5_never_marks_within_5_bars_of_end() -> None:
    """TS-IND-013: a pivot needs `width` bars on each side; the last 5 bars are never marked."""
    # Pivot low at index 5 (value 1) and pivot high at 12, plus an extreme in the last 3 bars.
    low = arr(5, 5, 5, 5, 5, 1, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 6, 6, 0)
    high = low + 1.0
    high[12] = 20.0
    high[-2] = 50.0
    n = len(low)
    marks = p.pivots(high, low, 5)
    assert [(m.index, m.kind) for m in marks] == [(5, "low"), (12, "high")]
    assert marks[0].price == 1.0
    assert marks[1].price == 20.0
    assert [m.confirmed_at for m in marks] == [10, 17]
    assert all(m.index + 5 <= n - 1 for m in marks)
    hi_mask, lo_mask = p.pivot_masks(high, low, 5)
    assert not hi_mask[-5:].any()
    assert not lo_mask[-5:].any()
    assert p.pivot_confirmation_bar(5, 5) == 10
    # Not yet confirmed one bar earlier: truncating to 16 bars drops the pivot high at 12.
    assert [(m.index, m.kind) for m in p.pivots(high[:16], low[:16], 5)] == [(5, "low")]


def test_unit_pivots_strict_inequality_and_short_input() -> None:
    """TS-IND-013: ties are not pivots; series shorter than 2*width+1 have none."""
    flat = np.full(21, 3.0)
    assert p.pivots(flat, flat, 5) == []
    assert p.pivots(arr(1, 2, 3), arr(1, 2, 3), 5) == []
    low = arr(3, 3, 1, 3, 3, 3)
    hi_mask, lo_mask = p.pivot_masks(low + 1, low, 2)
    assert not hi_mask.any()
    assert list(np.flatnonzero(lo_mask)) == [2]
    # Equal neighbour on one side voids the pivot.
    low_tie = arr(3, 1, 1, 3, 3, 3)
    assert not p.pivot_masks(low_tie + 1, low_tie, 2)[1].any()


@given(
    st.lists(st.floats(1.0, 1000.0, allow_nan=False), min_size=0, max_size=60),
    st.integers(1, 6),
)
@settings(max_examples=100, deadline=None)
def test_prop_pivots_never_within_width_of_end_and_use_only_window(
    values: list[float], width: int
) -> None:
    """TS-IND-013: property form; every pivot has `width` bars each side and is a strict extreme."""
    low = np.array(values, dtype=np.float64)
    high = low + 0.5
    n = len(low)
    for m in p.pivots(high, low, width):
        assert width <= m.index <= n - 1 - width
        assert m.confirmed_at == m.index + width <= n - 1
        series = low if m.kind == "low" else high
        neighbours = [
            series[j] for j in range(m.index - width, m.index + width + 1) if j != m.index
        ]
        if m.kind == "low":
            assert all(series[m.index] < v for v in neighbours)
        else:
            assert all(series[m.index] > v for v in neighbours)


def test_unit_zigzag_compute_threshold_8pct_vs_3_atr_pct_uses_max() -> None:
    """TS-IND-014: threshold = max(8%, 3 * atr14/close).

    close 100: atr 2 -> 3*2% = 6% < 8% -> 0.08; atr 4 -> 12% -> 0.12; atr 8/close 200 -> 12%.
    NaN ATR (warm-up) falls back to the 8% floor.
    """
    atr = arr(2, 4, 8, NAN)
    close = arr(100, 100, 200, 100)
    assert_close(p.zigzag_threshold(atr, close), [0.08, 0.12, 0.12, 0.08])
    assert_close(
        p.zigzag_threshold(atr, close, min_pct=0.05, atr_mult=1.0), [0.05, 0.05, 0.05, 0.05]
    )
    assert_close(
        p.zigzag_threshold(atr, close, min_pct=0.01, atr_mult=1.0), [0.02, 0.04, 0.04, 0.01]
    )


def test_unit_zigzag_compute_confirmed_swings_and_tentative_extreme() -> None:
    """TS-IND-014: swing points on closes with a 5% reversal; worked by hand.

    closes 100,102,106,110,104,99,95,100,106,112,108, threshold 0.05.
    t2 106 >= 100*1.05 confirms the start low (idx 0, 100); highest close 110 at idx 3;
    t4 104 <= 110*0.95 = 104.5 confirms the high (idx 3); low runs to 95 at idx 6;
    t7 100 >= 95*1.05 = 99.75 confirms the low (idx 6); the high runs to 112 at idx 9;
    t10 108 > 112*0.95 = 106.4 so 112 stays tentative.
    """
    close = arr(100, 102, 106, 110, 104, 99, 95, 100, 106, 112, 108)
    zz = p.zigzag(close, 0.05)
    assert [(s.index, s.price, s.kind, s.confirmed_at) for s in zz.confirmed] == [
        (0, 100.0, "low", 2),
        (3, 110.0, "high", 4),
        (6, 95.0, "low", 7),
    ]
    assert zz.tentative == p.Swing(9, 112.0, "high", None)
    # Per-bar thresholds equal to the scalar give the same result.
    assert p.zigzag(close, np.full(len(close), 0.05)) == zz
    # At 12% the first reversal is 110 -> 96.8 (reached at 95), so the start low is never a
    # swing: confirmed high at 3, low at 6 (112 >= 95*1.12 = 106.4), tentative high at 9.
    big = p.zigzag(close, 0.12)
    assert [(s.index, s.kind) for s in big.confirmed] == [(3, "high"), (6, "low")]
    assert p.zigzag(close, 0.5).confirmed == ()


def test_unit_zigzag_compute_downtrend_start_nan_and_trivial_inputs() -> None:
    """TS-IND-014: first leg down, NaN closes and NaN thresholds skipped, empty input."""
    down = p.zigzag(arr(100, 96, 90, 94.6, 99), 0.05)
    assert [(s.index, s.kind) for s in down.confirmed] == [(0, "high"), (2, "low")]
    assert down.tentative == p.Swing(4, 99.0, "high", None)
    skipped = p.zigzag(arr(100, NAN, 90, 100), arr(0.05, 0.05, NAN, 0.05))
    assert skipped.confirmed == ()
    assert skipped.tentative is None
    empty = p.zigzag(arr(), 0.05)
    assert empty.confirmed == ()
    assert empty.tentative is None
    # A pure up-then-down start never confirms until a reversal.
    assert p.zigzag(arr(100, 101, 102), 0.05).tentative is None


def _dates(*days: str) -> NDArray[np.datetime64]:
    return np.array(days, dtype="datetime64[D]")


def test_unit_resample_weekly_compute_friday_close_matches_manual() -> None:
    """TS-IND-015: weekly OHLCV by hand; partial current week included through the last bar."""
    # Mon 2026-11-02 .. Fri 11-06 then Mon 11-09 (partial week).
    d = _dates("2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-09")
    o = arr(10, 11, 14, 9, 9.5, 10.5)
    h = arr(12, 15, 14, 10, 11, 13)
    lo = arr(9, 10, 8, 8.5, 9, 10)
    c = arr(11, 14, 9, 9.5, 10.5, 12)
    v = arr(100, 200, 300, 400, 500, 600)
    w = p.resample_weekly(d, o, h, lo, c, v)
    assert list(w.week_ending) == list(_dates("2026-11-06", "2026-11-09"))
    assert_close(w.open, [10, 10.5])
    assert_close(w.high, [15, 13])
    assert_close(w.low, [8, 10])
    assert_close(w.close, [10.5, 12])
    assert_close(w.volume, [1500, 600])
    assert list(w.sessions) == [5, 1]
    assert list(w.week_index) == [0, 0, 0, 0, 0, 1]


def test_unit_resample_weekly_holiday_friday_labels_last_session_present() -> None:
    """TS-IND-015: Good Friday 2026-04-03 is closed, so the week is labeled Thursday 04-02."""
    d = _dates("2026-03-30", "2026-03-31", "2026-04-01", "2026-04-02", "2026-04-06")
    o = arr(1, 2, 3, 4, 5)
    h = arr(2, 3, 4, 9, 6)
    lo = arr(0.5, 1.5, 2.5, 3.5, 4.5)
    c = arr(1.5, 2.5, 3.5, 4.5, 5.5)
    v = arr(10, 10, 10, 10, 10)
    w = p.resample_weekly(d, o, h, lo, c, v)
    assert list(w.week_ending) == list(_dates("2026-04-02", "2026-04-06"))
    assert list(w.sessions) == [4, 1]
    assert_close(w.close, [4.5, 5.5])
    assert_close(w.high, [9, 6])
    # ISO year boundary: Wed 2025-12-31 and Fri 2026-01-02 share ISO week 2026-W01.
    y = p.resample_weekly(
        _dates("2025-12-26", "2025-12-31", "2026-01-02"),
        arr(1, 2, 3),
        arr(1, 2, 3),
        arr(1, 2, 3),
        arr(1, 2, 3),
        arr(1, 1, 1),
    )
    assert list(y.week_ending) == list(_dates("2025-12-26", "2026-01-02"))
    assert list(y.week_index) == [0, 1, 1]


def test_unit_resample_weekly_rejects_unsorted_and_handles_empty() -> None:
    """TS-IND-015: dates must be strictly ascending; empty input gives empty weekly arrays."""
    with pytest.raises(ValueError, match="ascending"):
        p.resample_weekly(
            _dates("2026-11-03", "2026-11-02"),
            arr(1, 1),
            arr(1, 1),
            arr(1, 1),
            arr(1, 1),
            arr(1, 1),
        )
    with pytest.raises(ValueError, match="length"):
        p.resample_weekly(_dates("2026-11-03"), arr(1, 1), arr(1), arr(1), arr(1), arr(1))
    e = p.resample_weekly(_dates(), arr(), arr(), arr(), arr(), arr())
    assert len(e.week_ending) == 0
    assert len(e.week_index) == 0
    assert len(e.close) == 0


def test_unit_resample_weekly_matches_data_resample_on_fixture_provider() -> None:
    """TS-IND-015: array resample equals supertrends.data.resample on fixture daily bars."""
    universe = FixtureUniverse(seed=20261114, end_date=date(2026, 11, 13))
    market = FixtureProvider(universe)
    symbol = FixtureUniverse.symbols()[0]
    bars = market.daily_bars(symbol, date(2025, 1, 1), date(2026, 11, 13))
    assert len(bars) > 300
    rows = [DailyRow(b.ts.date(), b.open, b.high, b.low, b.close, b.volume) for b in bars]
    expected = data_resample_weekly(rows)
    got = p.resample_weekly(
        np.array([r.date for r in rows], dtype="datetime64[D]"),
        np.array([r.open for r in rows]),
        np.array([r.high for r in rows]),
        np.array([r.low for r in rows]),
        np.array([r.close for r in rows]),
        np.array([float(r.volume) for r in rows]),
    )
    assert len(got.week_ending) == len(expected)
    for i, wk in enumerate(expected):
        assert got.week_ending[i] == np.datetime64(wk.week_ending, "D")
        assert (got.open[i], got.high[i], got.low[i], got.close[i]) == (
            wk.open,
            wk.high,
            wk.low,
            wk.close,
        )
        assert got.volume[i] == wk.volume
        assert got.sessions[i] == wk.sessions
    # week_index maps each daily bar to the weekly bar that contains it.
    for day, idx in zip((r.date for r in rows), got.week_index, strict=True):
        assert day <= expected[idx].week_ending
        assert idx == 0 or day > expected[idx - 1].week_ending


_FLOATS = st.floats(1.0, 500.0, allow_nan=False)


@given(
    st.lists(st.tuples(_FLOATS, _FLOATS, _FLOATS), min_size=0, max_size=80),
    st.integers(2, 20),
)
@settings(max_examples=60, deadline=None)
def test_prop_primitives_compute_output_length_equals_input_nan_warmup(
    rows: list[tuple[float, float, float]], n: int
) -> None:
    """TS-IND-016: same-length output and NaN exactly where the warm-up rule says."""
    m = len(rows)
    close = np.array([r[0] for r in rows], dtype=np.float64)
    low = np.minimum(close, np.array([r[1] for r in rows], dtype=np.float64))
    high = np.maximum(close, np.array([r[2] for r in rows], dtype=np.float64))
    volume = np.array([r[1] * 10 for r in rows], dtype=np.float64)

    def nan_count(a: NDArray[np.float64]) -> int:
        assert len(a) == m
        assert a.dtype == np.float64
        # NaN only at the start (a contiguous warm-up), never after the first value.
        k = int(np.isnan(a).sum())
        assert np.isnan(a[:k]).all()
        assert not np.isnan(a[k:]).any()
        return k

    for fn in (p.sma, p.ema, p.rma, p.stdev, p.percentile_rank, p.linreg_slope):
        assert nan_count(fn(close, n)) == min(n - 1, m), fn.__name__
    assert nan_count(p.true_range(high, low, close)) == 0
    assert nan_count(p.atr(high, low, close, n)) == min(n - 1, m)
    assert nan_count(p.rsi(close, n)) == min(n, m)
    assert nan_count(p.obv(close, volume)) == 0
    rsi = p.rsi(close, n)
    finite = rsi[~np.isnan(rsi)]
    assert ((finite >= 0.0) & (finite <= 100.0)).all()


def test_unit_primitives_warmup_positions_by_function() -> None:
    """TS-IND-016: exact warm-up lengths (documented in each docstring) on 30 bars, n=5."""
    x = np.array(_wave(30))
    high, low = x + 1, x - 1
    first_valid = {
        "sma": (p.sma(x, 5), 4),
        "ema": (p.ema(x, 5), 4),
        "rma": (p.rma(x, 5), 4),
        "stdev": (p.stdev(x, 5), 4),
        "percentile_rank": (p.percentile_rank(x, 5), 4),
        "linreg_slope": (p.linreg_slope(x, 5), 4),
        "true_range": (p.true_range(high, low, x), 0),
        "atr": (p.atr(high, low, x, 5), 4),
        "rsi": (p.rsi(x, 5), 5),
        "obv": (p.obv(x, np.ones(30)), 0),
    }
    for name, (values, first) in first_valid.items():
        assert len(values) == 30, name
        assert np.isnan(values[:first]).all(), name
        assert not np.isnan(values[first:]).any(), name


def test_unit_primitives_reject_bad_window() -> None:
    """TS-IND-016: n < 1 (n < 2 for rank) raises ValueError."""
    with pytest.raises(ValueError, match="window"):
        p.sma(SERIES, 0)
    with pytest.raises(ValueError, match="window"):
        p.percentile_rank(SERIES, 1)
    with pytest.raises(ValueError, match="width"):
        p.pivots(SERIES, SERIES, 0)
    with pytest.raises(ValueError, match="length"):
        p.true_range(arr(1, 2), arr(1), arr(1, 2))
    with pytest.raises(ValueError, match="length"):
        p.obv(arr(1, 2), arr(1))
    with pytest.raises(ValueError, match="threshold"):
        p.zigzag(arr(1, 2, 3), arr(0.1, 0.1))


def test_unit_indicators_all_aggregation_exposes_primitives() -> None:
    """TS-IND-017: supertrends.indicators.__all__ aggregates every module's __all__."""
    expected = [
        "sma",
        "ema",
        "rma",
        "stdev",
        "true_range",
        "atr",
        "rsi",
        "obv",
        "percentile_rank",
        "linreg_slope",
        "pivots",
        "zigzag",
        "zigzag_threshold",
        "resample_weekly",
    ]
    for name in expected:
        assert name in indicators.__all__
        assert getattr(indicators, name) is getattr(p, name)
    modules = [
        "divergence",
        "fibonacci",
        "flow",
        "levels",
        "meanrev",
        "momentum",
        "primitives",
        "supertrend",
        "trend",
        "volatility",
        "volume",
    ]
    combined: list[str] = []
    for mod in modules:
        module = importlib.import_module(f"supertrends.indicators.{mod}")
        combined += module.__all__
    assert sorted(indicators.__all__) == sorted(combined)
    assert len(set(indicators.__all__)) == len(indicators.__all__)
    assert all(hasattr(indicators, name) for name in indicators.__all__)
