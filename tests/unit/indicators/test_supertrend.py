# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Supertrend tests (TS-IND-020, 023 to 036).

The TradingView parity rows (TS-IND-021, 022) live in tests/golden/test_tradingview_parity.py.
Expected values come from tests/golden/handcomputed/supertrend_40bar.json, derived by the
independent plain-Python script next to it, or are checked by hand in comments here.
"""

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from supertrends.indicators import primitives as p
from supertrends.indicators import supertrend as m
from supertrends.indicators.supertrend import supertrend
from tests.golden.tradingview_support import parse_export, tv_direction_to_internal

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "golden" / "handcomputed" / "supertrend_40bar.json"
TOL = 1e-9
NAN = math.nan
F64 = NDArray[np.float64]


def arr(values: list[Any]) -> F64:
    return np.array([NAN if v is None else v for v in values], dtype=np.float64)


def load_fixture() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text())
    return data


def run_fixture() -> tuple[dict[str, Any], m.SupertrendResult]:
    fx = load_fixture()
    res = supertrend(arr(fx["high"]), arr(fx["low"]), arr(fx["close"]), fx["atr_length"], fx["factor"])
    return fx, res


# --- TS-IND-020 -----------------------------------------------------------------------------


def test_golden_supertrend_compute_handcomputed_40_bar_both_flips_and_ratcheting_matches() -> None:
    """TS-IND-020: hand-computed 40-bar case (atr_length 3, factor 1.5) from the first defined bar.

    By-hand checks (also asserted below), high = close + 1 and low = close - 1:
    * bar 2: TR = 2, 2, 2 so atr = 2; hl2 = 98; basic_up = 101, basic_lo = 95; atr[1] is undefined
      so dir = -1 and st = final_up = 101.
    * bar 11 (up flip): TR10 = 3 (high 96 vs close 93), TR11 = 4 (high 99 vs close 95);
      atr10 = (2*2 + 3)/3 = 7/3, atr11 = (2*7/3 + 4)/3 = 26/9; hl2 = 98; basic_lo = 98 - 1.5*26/9
      = 93.6667; final_up stays 96 (basic_up 102.33 not below 96, close[10] = 95 not above 96);
      st[10] == final_up[10] and close 98 > 96, so dir = +1 and st = final_lo = 93.6667.
    * bar 30 (down flip): close 117 < final_lo 117.8824, so dir = -1 and st = final_up = 121.3968.
    """
    fx, res = run_fixture()
    for name, got in (
        ("atr", res.atr),
        ("final_upper", res.final_upper),
        ("final_lower", res.final_lower),
        ("line", res.line),
        ("direction", res.direction),
    ):
        want = arr(fx[name])
        np.testing.assert_array_equal(np.isnan(got), np.isnan(want), err_msg=name)
        ok = ~np.isnan(want)
        np.testing.assert_allclose(got[ok], want[ok], atol=TOL, rtol=0, err_msg=name)
    assert res.direction[2] == -1
    assert res.line[2] == pytest.approx(101.0, abs=TOL)
    assert res.direction[11] == 1
    assert res.line[11] == pytest.approx(98 - 1.5 * 26 / 9, abs=TOL)
    assert res.direction[30] == -1
    assert res.line[30] == pytest.approx(121.3968460919474, abs=TOL)
    assert res.direction[29] == 1


def test_golden_supertrend_fixture_covers_flips_and_ratchets() -> None:
    """TS-IND-020: the fixture really contains both flips and ratcheting of both bands."""
    fx = load_fixture()
    d = [x for x in fx["direction"] if x is not None]
    flips = [(a, b) for a, b in zip(d, d[1:], strict=False) if a != b]
    assert (-1, 1) in flips
    assert (1, -1) in flips
    fu = [x for x in fx["final_upper"] if x is not None]
    fl = [x for x in fx["final_lower"] if x is not None]
    assert any(b == a for a, b in zip(fu, fu[1:], strict=False))
    assert any(b < a for a, b in zip(fu, fu[1:], strict=False))
    assert any(b == a for a, b in zip(fl, fl[1:], strict=False))
    assert any(b > a for a, b in zip(fl, fl[1:], strict=False))


# --- TS-IND-023 / 024 -----------------------------------------------------------------------


def test_unit_supertrend_tv_boundary_conversion_negative_tv_direction_maps_to_plus_1_up() -> None:
    """TS-IND-023: TradingView -1 (up) converts to internal +1."""
    assert tv_direction_to_internal(-1.0) == 1.0
    assert tv_direction_to_internal(-1) == 1.0


def test_unit_supertrend_tv_boundary_conversion_positive_tv_direction_maps_to_minus_1_down() -> None:
    """TS-IND-024: TradingView +1 (down) converts to internal -1; zero and NaN are rejected."""
    assert tv_direction_to_internal(1.0) == -1.0
    with pytest.raises(ValueError, match="non-zero"):
        tv_direction_to_internal(0.0)
    with pytest.raises(ValueError, match="non-zero"):
        tv_direction_to_internal(NAN)


def test_unit_supertrend_tv_export_parse_both_column_variants() -> None:
    """TS-IND-024: the export parser handles Up/Down Trend plots and Supertrend plus Direction."""
    plots = (
        "time,open,high,low,close,Volume,Up Trend,Down Trend\n"
        "1,1,2,1,2,5,,\n"
        "2,1,3,1,2,5,1.5,\n"
        "3,1,3,1,2,5,,2.5\n"
    )
    a = parse_export(plots)
    np.testing.assert_array_equal(a.direction, [NAN, 1.0, -1.0])
    np.testing.assert_array_equal(a.line, [NAN, 1.5, 2.5])
    np.testing.assert_array_equal(a.close, [2.0, 2.0, 2.0])
    single = "time,High,Low,Close,Supertrend,Direction\n1,2,1,2,,\n2,3,1,2,1.5,-1\n3,3,1,2,2.5,1\n"
    b = parse_export(single)
    np.testing.assert_array_equal(b.direction, [NAN, 1.0, -1.0])
    np.testing.assert_array_equal(b.line, [NAN, 1.5, 2.5])
    with pytest.raises(ValueError, match="both"):
        parse_export("high,low,close,Up Trend,Down Trend\n2,1,2,1,2\n")
    with pytest.raises(ValueError, match="high, low and close"):
        parse_export("time,open\n1,1\n")
    with pytest.raises(ValueError, match="Up Trend and Down Trend columns"):
        parse_export("high,low,close\n2,1,2\n")


# --- TS-IND-025 to 029 ----------------------------------------------------------------------


def test_unit_supertrend_compute_atr_undefined_prior_bar_direction_minus_1() -> None:
    """TS-IND-025: NaN before atr is defined; the first defined bar is down whatever the price."""
    # Rising prices, atr_length 3: atr defined from bar 2, yet dir[2] = -1 and st = final_up.
    close = np.arange(10.0, 20.0)
    res = supertrend(close + 1, close - 1, close, 3, 1.5)
    assert np.isnan(res.direction[:2]).all()
    assert np.isnan(res.line[:2]).all()
    assert res.direction[2] == -1
    assert res.line[2] == res.final_upper[2]


def test_unit_supertrend_compute_final_up_ratchets_down_only_while_close_stays_below() -> None:
    """TS-IND-026: final_up never rises unless the prior close was above the prior final_up."""
    fx, res = run_fixture()
    close = arr(fx["close"])
    fu = res.final_upper
    seen_reset = seen_hold = seen_lower = False
    for t in range(3, 40):
        if close[t - 1] > fu[t - 1]:
            seen_reset = True  # free to move: at bar 15 it jumps up from 105.89 to 112.84
            assert fu[t] != fu[t - 1]
        else:
            assert fu[t] <= fu[t - 1]
            seen_hold |= fu[t] == fu[t - 1]
            seen_lower |= fu[t] < fu[t - 1]
    assert seen_reset
    assert seen_hold
    assert seen_lower
    assert fu[15] > fu[14]


def test_unit_supertrend_compute_final_lo_ratchets_up_only_while_close_stays_above() -> None:
    """TS-IND-027: final_lo never falls unless the prior close was below the prior final_lo."""
    fx, res = run_fixture()
    close = arr(fx["close"])
    fl = res.final_lower
    seen_reset = seen_hold = seen_higher = False
    for t in range(3, 40):
        if close[t - 1] < fl[t - 1]:
            seen_reset = True  # bar 9: close[8] = 94 < 95 so it drops to 90
            assert fl[t] != fl[t - 1]
        else:
            assert fl[t] >= fl[t - 1]
            seen_hold |= fl[t] == fl[t - 1]
            seen_higher |= fl[t] > fl[t - 1]
    assert seen_reset
    assert seen_hold
    assert seen_higher
    assert fl[9] < fl[8]


def test_unit_supertrend_compute_flip_up_when_close_exceeds_final_up() -> None:
    """TS-IND-028: bar 11: close 98 > final_up 96 while the line was final_up, so direction +1."""
    _, res = run_fixture()
    assert res.direction[10] == -1
    assert res.direction[11] == 1
    assert res.final_upper[11] == 96.0
    assert res.line[11] == res.final_lower[11]


def test_unit_supertrend_compute_flip_down_when_close_below_final_lo() -> None:
    """TS-IND-029: bar 30: close 117 < final_lo 117.88 while the line was final_lo, so -1."""
    fx, res = run_fixture()
    assert res.direction[29] == 1
    assert res.direction[30] == -1
    assert arr(fx["close"])[30] < res.final_lower[30]
    assert res.line[30] == res.final_upper[30]


def test_unit_supertrend_compute_nan_and_short_inputs() -> None:
    """Inputs shorter than the ATR window give all NaN; NaN prices poison the rest."""
    x = np.array([1.0, 2.0])
    res = supertrend(x + 1, x, x, 5, 3.0)
    assert np.isnan(res.line).all()
    assert np.isnan(res.direction).all()
    assert supertrend(x[:0], x[:0], x[:0]).line.shape == (0,)
    close = np.arange(10.0, 30.0)
    high = close + 1
    high[12] = NAN
    res = supertrend(high, close - 1, close, 3, 1.5)
    assert not np.isnan(res.line[2:12]).any()
    assert np.isnan(res.line[12:]).all()
    with pytest.raises(ValueError, match="same length"):
        supertrend(x, x[:1], x)
    with pytest.raises(ValueError, match="atr_length"):
        supertrend(x, x, x, 0)


# --- TS-IND-030 / 031: properties ------------------------------------------------------------


@st.composite
def ohlc(draw: st.DrawFn) -> tuple[F64, F64, F64]:
    n = draw(st.integers(min_value=1, max_value=120))
    steps = draw(st.lists(st.floats(-0.08, 0.08), min_size=n, max_size=n))
    ups = draw(st.lists(st.floats(0.0, 0.06), min_size=n, max_size=n))
    downs = draw(st.lists(st.floats(0.0, 0.06), min_size=n, max_size=n))
    close = 100.0 * np.exp(np.cumsum(steps))
    # Close anywhere inside the bar: high and low bracket close.
    return close * (1 + np.array(ups)), close * (1 - np.array(downs)), close


@settings(max_examples=300, deadline=None)
@given(data=ohlc(), n=st.integers(1, 12), factor=st.floats(0.1, 5.0))
def test_prop_supertrend_compute_direction_always_plus_or_minus_1_after_warmup(
    data: tuple[F64, F64, F64], n: int, factor: float
) -> None:
    """TS-IND-030: direction is NaN before atr is defined and exactly +1 or -1 afterwards."""
    high, low, close = data
    res = supertrend(high, low, close, n, factor)
    warm = np.isnan(res.atr)
    assert np.isnan(res.direction[warm]).all()
    assert np.isin(res.direction[~warm], (1.0, -1.0)).all()
    assert not np.isnan(res.line[~warm]).any()


@settings(max_examples=300, deadline=None)
@given(data=ohlc(), n=st.integers(1, 12), factor=st.floats(1.0, 5.0))
def test_prop_supertrend_compute_line_below_close_when_up_above_close_when_down(
    data: tuple[F64, F64, F64], n: int, factor: float
) -> None:
    """TS-IND-031: line <= close when up and line >= close when down.

    Scope, found by fuzzing the formula: the first defined bar is forced down by the spec's
    warm-up rule and its line is hl2 + factor * atr, which can sit below a close near the high;
    and with a factor under about 0.5 the two bands can cross after a flip, putting the new line
    on the wrong side of close. Both are properties of TradingView's formula, which we match, so
    the invariant is asserted for factor >= 1 (the configured default is 3.0) after the first
    defined bar. Equality is allowed: a close exactly on the lower band keeps the trend up
    (flip needs `close < final_lo`), and exactly on the upper band keeps it down (flip up needs
    `close > final_up`), so the inequalities are non-strict. Every stay-branch bar satisfies the
    invariant by the branch test itself; a flip bar puts the line on the opposite band, which
    for factor >= 1 lies beyond close (checked here, not proved for all inputs).
    """
    high, low, close = data
    res = supertrend(high, low, close, n, factor)
    up = res.direction == 1
    down = res.direction == -1
    up[n - 1 : n] = False
    down[n - 1 : n] = False
    assert (res.line[up] <= close[up]).all()
    assert (res.line[down] >= close[down]).all()


# --- TS-IND-032 / 033 / 035 -----------------------------------------------------------------


def test_unit_supertrend_derived_bars_since_flip_counts_from_last_flip() -> None:
    """TS-IND-032: 0 on a flip bar, then 1, 2, ...; the first defined bar is 0; NaN in warm-up."""
    d = np.array([NAN, NAN, -1, -1, 1, 1, 1, -1, 1])
    got = m.bars_since_flip(d)
    np.testing.assert_array_equal(got, [NAN, NAN, 0, 1, 0, 1, 2, 0, 0])
    assert m.bars_since_flip(np.zeros(0)).shape == (0,)


def test_unit_supertrend_derived_distance_atr_signed_close_minus_st_over_atr() -> None:
    """TS-IND-033: (close - line) / atr; (10 - 9) / 2 = 0.5 and (8 - 9) / 2 = -0.5."""
    close = np.array([10.0, 8.0, 10.0, 10.0, 10.0])
    line = np.array([9.0, 9.0, 9.0, NAN, 9.0])
    atr = np.array([2.0, 2.0, NAN, 2.0, 0.0])
    np.testing.assert_allclose(m.distance_atr(close, line, atr), [0.5, -0.5, NAN, NAN, NAN], atol=TOL)
    fx, res = run_fixture()
    got = m.distance_atr(arr(fx["close"]), res.line, res.atr)
    # Bar 29: close 121, line 117.8824, atr 2.0784 gives 1.5 (the 1.5 factor: line = hl2 - 1.5 atr).
    assert got[29] == pytest.approx((121 - 117.88241597275632) / 2.0783893514957823, abs=TOL)
    assert np.isnan(got[:2]).all()


def test_unit_supertrend_derived_st_line_equals_invalidation_level() -> None:
    """TS-IND-035: `line` is final_lower when up and final_upper when down."""
    _, res = run_fixture()
    ok = ~np.isnan(res.line)
    up = ok & (res.direction == 1)
    down = ok & (res.direction == -1)
    np.testing.assert_array_equal(res.line[up], res.final_lower[up])
    np.testing.assert_array_equal(res.line[down], res.final_upper[down])


# --- TS-IND-034: weekly direction -------------------------------------------------------------


def weekly_inputs(weeks: int = 16) -> tuple[Any, F64, F64, F64, F64, F64]:
    days = np.array(
        [np.datetime64("2024-01-01") + np.timedelta64(7 * w + d, "D") for w in range(weeks) for d in range(5)]
    )
    rng = np.random.default_rng(7)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, len(days))))
    high = close * (1 + rng.uniform(0, 0.015, len(days)))
    low = close * (1 - rng.uniform(0, 0.015, len(days)))
    return days, close, high, low, close, np.full(len(days), 1000.0)


def test_unit_supertrend_derived_weekly_direction_uses_resampled_weekly_bars() -> None:
    """TS-IND-034: weekly direction is Supertrend on weekly bars, as known at each day (no leak).

    Oracle: for every day t, resample the data truncated at t (so the current week holds only
    bars <= t) and take the last Supertrend direction. The incremental O(n) implementation must
    equal it. On the final day it also equals Supertrend on the full weekly bars.
    """
    days, open_, high, low, close, vol = weekly_inputs()
    got = m.supertrend_weekly_direction(days, open_, high, low, close, vol, 3, 1.5)
    for t in range(len(days)):
        wb = p.resample_weekly(days[: t + 1], open_[: t + 1], high[: t + 1], low[: t + 1], close[: t + 1], vol[: t + 1])
        want = supertrend(wb.high, wb.low, wb.close, 3, 1.5).direction[-1]
        assert (math.isnan(want) and math.isnan(got[t])) or got[t] == want, t
    wb = p.resample_weekly(days, open_, high, low, close, vol)
    final = supertrend(wb.high, wb.low, wb.close, 3, 1.5).direction
    assert got[-1] == final[-1]
    assert np.isnan(got[:10]).all()  # fewer than 3 weekly bars: ATR undefined
    assert not np.isnan(got[10:]).any()
    assert set(np.unique(got[10:])) <= {-1.0, 1.0}
    assert len(np.unique(got[10:])) == 2  # fixture data flips at least once


def test_unit_supertrend_derived_weekly_direction_truncation_invariant_and_defaults() -> None:
    """TS-IND-034: truncating the input never changes earlier days (no look-ahead); defaults 10/3."""
    days, open_, high, low, close, vol = weekly_inputs(30)
    full = m.supertrend_weekly_direction(days, open_, high, low, close, vol)
    for cut in (37, 80, 101, 149):
        part = m.supertrend_weekly_direction(
            days[:cut], open_[:cut], high[:cut], low[:cut], close[:cut], vol[:cut]
        )
        np.testing.assert_array_equal(part, full[:cut])
    empty = np.zeros(0)
    assert m.supertrend_weekly_direction(days[:0], empty, empty, empty, empty, empty).shape == (0,)


# --- TS-IND-036 -------------------------------------------------------------------------------


def test_unit_supertrend_params_non_default_length_and_factor_from_config() -> None:
    """TS-IND-036: the config's atr_length and factor are passed through explicitly.

    The indicator never reads config; this test does, and also checks a non-default pair
    changes the result (a 5-length, factor-2 line differs from the 10, 3 line).
    """
    cfg = yaml.safe_load((ROOT / "config" / "scoring.yaml").read_text())["supertrend"]
    assert (cfg["atr_length"], cfg["factor"]) == (10, 3.0)
    fx = load_fixture()
    high, low, close = arr(fx["high"]), arr(fx["low"]), arr(fx["close"])
    from_cfg = supertrend(high, low, close, cfg["atr_length"], cfg["factor"])
    default = supertrend(high, low, close)
    np.testing.assert_array_equal(from_cfg.line, default.line)
    assert np.isnan(from_cfg.line[:9]).all()
    assert not np.isnan(from_cfg.line[9])
    other = supertrend(high, low, close, 5, 2.0)
    assert np.isnan(other.line[:4]).all()
    assert not np.isnan(other.line[4])
    assert not np.array_equal(other.line, default.line, equal_nan=True)
    # Bar 4 by hand, atr_length 5, factor 2: TR = 2, 2, 2, 2, 2 -> atr 2; hl2 = 96; final_up = 100.
    assert other.atr[4] == pytest.approx(2.0, abs=TOL)
    assert other.final_upper[4] == pytest.approx(100.0, abs=TOL)
    assert other.direction[4] == -1
