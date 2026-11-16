# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Ripster EMA Clouds tests (TS-IND-133 to 140, 143 to 146; PRD 7.13, FR-224).

The TradingView parity rows (TS-IND-141, 142) live in tests/golden/test_ripster_parity.py.
Expected values come from tests/golden/handcomputed/ripster_clouds.json, derived by the
independent plain-Python script next to it, or are checked by hand in comments here.
"""

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from supertrends.indicators import primitives as p
from supertrends.indicators import registry as reg
from supertrends.indicators.ripster_clouds import (
    RIPSTER_CLOUDS,
    EmaCloud,
    bars_since_stack_flip,
    cloud_stack,
    ema_cloud,
    ripster_clouds,
    ripster_pullback,
    ripster_weekly_direction,
)
from tests.golden.tradingview_support import parse_ripster_export
from tests.unit.indicators.lookahead_support import check_entry, make_bundle

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "golden" / "handcomputed" / "ripster_clouds.json"
TOL = 1e-9
NAN = math.nan
F64 = NDArray[np.float64]
NAMES = (
    "bars_since_stack_flip",
    "cloud_stack",
    "ema_cloud",
    "ripster_clouds",
    "ripster_pullback",
    "ripster_weekly_direction",
)


def arr(values: list[Any]) -> F64:
    return np.array([NAN if v is None else v for v in values], dtype=np.float64)


def load_fixture() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text())
    return data


def same(got: F64, want: F64) -> bool:
    """Equal NaN masks and values within TOL."""
    if not np.array_equal(np.isnan(got), np.isnan(want)):
        return False
    ok = ~np.isnan(want)
    return bool(np.all(np.abs(got[ok] - want[ok]) <= TOL))


def cloud(top: list[float], bot: list[float]) -> EmaCloud:
    """An EmaCloud built from edges only (direction +1, pos 0); enough for stack and pullback."""
    t, b = np.array(top), np.array(bot)
    one = np.ones(len(t))
    return EmaCloud(ema_short=t, ema_long=b, top=t, bot=b, direction=one, pos=0 * one)


# --- TS-IND-133 -----------------------------------------------------------------------------


def test_golden_ripster_clouds_handcomputed_fixture_top_bot_dir_pos_stack_match_every_bar() -> (
    None
):
    """TS-IND-133: every cloud field, stack, bars since flip and pullback match the derivation."""
    fx = load_fixture()
    clouds = tuple((int(s), int(lg)) for s, lg in fx["clouds"])
    res = ripster_clouds(
        arr(fx["high"]), arr(fx["low"]), arr(fx["close"]), clouds, fx["pullback_lookback"]
    )
    assert len(res.clouds) == 5
    for i, (got, want) in enumerate(zip(res.clouds, fx["cloud"], strict=True)):
        for field in ("ema_short", "ema_long", "top", "bot", "direction", "pos"):
            assert same(getattr(got, field), arr(want[field])), f"c{i + 1}.{field}"
    assert same(res.stack, arr(fx["stack"]))
    assert same(res.bars_since_stack_flip, arr(fx["bars_since_stack_flip"]))
    assert same(res.pullback, arr(fx["pullback"]))


def test_golden_ripster_clouds_fixture_covers_flips_inside_close_and_pullbacks() -> None:
    """TS-IND-133 coverage: the fixture really holds each case the task names."""
    fx = load_fixture()
    stack = arr(fx["stack"])
    pull = arr(fx["pullback"])
    pos = [arr(c["pos"]) for c in fx["cloud"]]
    steps = list(zip(stack[:-1], stack[1:], strict=True))
    assert any(a <= 0 < b for a, b in steps), "stack flip up"
    assert any(a >= 0 > b for a, b in steps), "stack flip down"
    assert any((x == 0).any() for x in pos), "close inside a cloud"
    assert (pull == 1).any(), "held bullish pullback"
    assert (pull == -1).any(), "held bearish pullback"
    close, low = arr(fx["close"]), arr(fx["low"])
    c1_top, c1_bot = arr(fx["cloud"][0]["top"]), arr(fx["cloud"][0]["bot"])
    failed = [
        t
        for t in range(2, len(close))
        if stack[t] == 1 and (low[t - 2 : t + 1] <= c1_top[t - 2 : t + 1]).any()
        and close[t] <= c1_bot[t]
    ]  # fmt: skip
    assert failed, "failed bullish pullback"
    assert all(pull[t] == 0 for t in failed)


def test_unit_ripster_clouds_fixture_rows_checked_by_hand() -> None:
    """Hand checks of a few fixture rows (hl2 = close because high = close + 1, low = close - 1).

    c1 is EMA 3 / 4. EMA 3 seeds at bar 2 with mean(100, 101, 100) = 100.333..; bar 3:
    100.333.. + 0.5 * (99 - 100.333..) = 99.666... EMA 4 seeds at bar 3 with
    mean(100, 101, 100, 99) = 100. So at bar 3 top = 100, bot = 99.666.., direction -1
    (short < long) and pos -1 (close 99 < bot).
    """
    fx = load_fixture()
    res = ripster_clouds(arr(fx["high"]), arr(fx["low"]), arr(fx["close"]), ((3, 4),) * 5, 3)
    c1 = res.clouds[0]
    assert math.isnan(c1.top[2])
    assert abs(c1.ema_short[3] - (100 + 1 / 3 + 0.5 * (99 - (100 + 1 / 3)))) <= TOL
    assert abs(c1.ema_long[3] - 100.0) <= TOL
    assert (c1.top[3], c1.direction[3], c1.pos[3]) == (100.0, -1.0, -1.0)


# --- TS-IND-134 -----------------------------------------------------------------------------


def test_unit_ripster_clouds_stack_flip_bars_since_stack_flip_counts_from_last_change_to_nonzero() -> (  # noqa: E501
    None
):
    """TS-IND-134: 0 on the flip bar in both directions, counting up; NaN while stack is 0."""
    stack = arr([None, None, 0, 1, 1, 1, -1, -1, 0, 0, -1, -1, 1])
    want = arr([None, None, None, 0, 1, 2, 0, 1, None, None, 0, 1, 0])
    assert same(bars_since_stack_flip(stack), want)
    # a run that starts nonzero counts from its first defined bar
    assert same(bars_since_stack_flip(arr([None, 1, 1])), arr([None, 0, 1]))
    assert bars_since_stack_flip(np.zeros(0)).shape == (0,)


# --- TS-IND-135 -----------------------------------------------------------------------------


def test_unit_ripster_clouds_ema_computed_on_hl2_for_all_ten_periods() -> None:
    """TS-IND-135: the default clouds are 8/9, 5/12, 34/50, 72/89, 180/200, each EMA on hl2."""
    assert RIPSTER_CLOUDS == ((8, 9), (5, 12), (34, 50), (72, 89), (180, 200))
    b = make_bundle(3, 400)
    res = ripster_clouds(b.high, b.low, b.close)
    hl2 = (b.high + b.low) / 2
    for c, (short, long) in zip(res.clouds, RIPSTER_CLOUDS, strict=True):
        assert same(c.ema_short, p.ema(hl2, short)), short
        assert same(c.ema_long, p.ema(hl2, long)), long
        assert same(c.top, np.maximum(c.ema_short, c.ema_long))
        assert not same(c.ema_short, p.ema(b.close, short))  # hl2, not close


# --- TS-IND-136 -----------------------------------------------------------------------------


def test_unit_ripster_clouds_close_inside_cloud_pos_is_zero() -> None:
    """TS-IND-136: pos 0 inside the cloud (edges included), +1 above top, -1 below bot."""
    # EMA 1 is the source itself, so ema_short = src and ema_long = EMA 2 of src.
    src = np.array([10.0, 12.0, 11.0, 11.0, 11.0])
    # EMA 2 seeds at bar 1 with 11, then 11 + (2/3)(11 - 11) = 11 ... and the short is src
    close = np.array([0.0, 13.0, 11.0, 10.0, 11.0])
    c = ema_cloud(src, close, 1, 2)
    assert math.isnan(c.pos[0])
    assert (c.top[1], c.bot[1]) == (12.0, 11.0)
    assert c.pos[1] == 1.0  # 13 above top 12
    assert c.pos[2] == 0.0  # on both edges (top = bot = 11): inside
    assert c.pos[3] == -1.0  # 10 below bot 11
    assert c.direction[1] == 1.0  # short 12 > long 11
    assert c.direction[2] == -1.0  # equal EMAs are not "short above long"


# --- TS-IND-137 to 139 ----------------------------------------------------------------------


def _pullback_case(lows: list[float], highs: list[float], closes: list[float], s: float) -> F64:
    n = len(closes)
    c1 = cloud([100.0] * n, [98.0] * n)  # c1 top 100, bot 98 on every bar
    return ripster_pullback(np.array(highs), np.array(lows), np.array(closes), c1, np.full(n, s))


def test_unit_ripster_pullback_held_low_tests_c1_within_3_bars_and_close_above_bot_flag_true() -> (
    None
):
    """TS-IND-137: stack +1, a low <= top(c1) 2 bars ago, close > bot(c1): +1 (held)."""
    lows = [101.0, 101.0, 99.5, 98.5, 101.0]
    got = _pullback_case(lows, [x + 3 for x in lows], [103.0, 103.0, 100.0, 99.0, 102.0], 1.0)
    assert got[4] == 1.0
    assert got[3] == 1.0  # close 99 still above bot 98
    # bearish mirror: stack -1, a high >= bot(c1) within 3 bars, close < top(c1): -1
    highs = [97.0, 97.0, 98.5, 97.0, 97.0]
    got = _pullback_case([x - 3 for x in highs], highs, [95.0, 95.0, 97.0, 96.0, 95.0], -1.0)
    assert got[4] == -1.0


def test_unit_ripster_pullback_failed_close_at_or_below_bot_c1_flag_false() -> None:
    """TS-IND-138: the same test with close <= bot(c1) is a failed pullback: 0."""
    lows = [101.0, 101.0, 99.5, 97.0, 96.0]
    got = _pullback_case(lows, [x + 3 for x in lows], [103.0, 103.0, 100.0, 98.0, 97.0], 1.0)
    assert got[3] == 0.0  # close equal to bot is not above it
    assert got[4] == 0.0
    highs = [97.0, 97.0, 98.5, 101.0]
    got = _pullback_case([x - 3 for x in highs], highs, [95.0, 95.0, 97.0, 100.0], -1.0)
    assert got[3] == 0.0  # bearish: close at top(c1) is not below it


def test_unit_ripster_pullback_stale_test_4_bars_ago_flag_false() -> None:
    """TS-IND-139: the window is the last 3 bars (t-2 to t); a test at t-3 or t-4 is stale."""
    lows = [99.0, 101.0, 101.0, 101.0, 101.0]
    closes = [103.0] * 5
    got = _pullback_case(lows, [104.0] * 5, closes, 1.0)
    assert got[2] == 1.0  # the test is the third-last bar: counts
    assert got[3] == 0.0  # three bars ago: stale
    assert got[4] == 0.0  # four bars ago: stale
    # stack 0 never flags, even with a fresh test
    assert (_pullback_case(lows, [104.0] * 5, closes, 0.0) == 0).all()


def test_unit_ripster_pullback_lookback_parameter_and_nan_policy() -> None:
    """The lookback comes from config (`ripster.pullback_lookback_bars`); NaN stack gives NaN."""
    n = 5
    c1 = cloud([100.0] * n, [98.0] * n)
    lows, closes = np.array([99.0, 101, 101, 101, 101]), np.full(n, 103.0)
    got = ripster_pullback(lows + 5, lows, closes, c1, np.ones(n), lookback=5)
    assert got[4] == 1.0
    stack = arr([None, 1, 1, 1, 1])
    assert math.isnan(ripster_pullback(lows + 5, lows, closes, c1, stack)[0])


# --- TS-IND-140 -----------------------------------------------------------------------------


def weekly_inputs(n_weeks: int = 70) -> tuple[NDArray[np.datetime64], F64, F64, F64, F64, F64]:
    """Five sessions a week from Monday 2024-01-01, a slow sine trend so the cloud flips."""
    days = np.array(
        [
            np.datetime64("2024-01-01") + np.timedelta64(7 * w + d, "D")
            for w in range(n_weeks)
            for d in range(5)
        ]
    )
    rng = np.random.default_rng(11)
    drift = 0.01 * np.sin(np.arange(len(days)) / 40.0)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.006)))
    high = close * (1 + rng.uniform(0, 0.015, len(days)))
    low = close * (1 - rng.uniform(0, 0.015, len(days)))
    return days, close, high, low, close, np.full(len(days), 1000.0)


def test_unit_ripster_clouds_weekly_34_50_direction_uses_resampled_weekly_bars() -> None:
    """TS-IND-140: `rc_dir_w` is the cloud direction on weekly bars, as known at each day.

    Oracle: for every day t, resample the data truncated at t (so the current week holds only
    bars <= t) and take the last weekly cloud direction. Small periods (3/5) keep it cheap.
    """
    days, open_, high, low, close, vol = weekly_inputs(30)
    got = ripster_weekly_direction(days, open_, high, low, close, vol, 3, 5)
    for t in range(len(days)):
        wb = p.resample_weekly(
            days[: t + 1], open_[: t + 1], high[: t + 1], low[: t + 1], close[: t + 1], vol[: t + 1]
        )
        want = ema_cloud((wb.high + wb.low) / 2, wb.close, 3, 5).direction[-1]
        assert (math.isnan(want) and math.isnan(got[t])) or got[t] == want, t
    assert np.isnan(got[:20]).all()  # fewer than 5 weekly bars
    assert not np.isnan(got[20:]).any()
    assert set(np.unique(got[20:])) == {-1.0, 1.0}


def test_unit_ripster_clouds_weekly_direction_defaults_34_50_and_truncation_invariant() -> None:
    """TS-IND-140: defaults are 34/50 (NaN before 50 weeks); truncation never changes the past."""
    days, open_, high, low, close, vol = weekly_inputs()
    full = ripster_weekly_direction(days, open_, high, low, close, vol)
    assert np.isnan(full[: 49 * 5]).all()
    assert not np.isnan(full[49 * 5 :]).any()
    for cut in (251, 300, 349):
        part = ripster_weekly_direction(
            days[:cut], open_[:cut], high[:cut], low[:cut], close[:cut], vol[:cut]
        )
        np.testing.assert_array_equal(part, full[:cut])
    empty = np.zeros(0)
    assert ripster_weekly_direction(days[:0], empty, empty, empty, empty, empty).shape == (0,)


# --- TS-IND-143 / 144 -----------------------------------------------------------------------


@st.composite
def ohlc(draw: st.DrawFn) -> tuple[F64, F64, F64]:
    n = draw(st.integers(1, 120))
    rets = draw(st.lists(st.floats(-0.08, 0.08), min_size=n, max_size=n))
    ups = draw(st.lists(st.floats(0, 0.05), min_size=n, max_size=n))
    downs = draw(st.lists(st.floats(0, 0.05), min_size=n, max_size=n))
    close = 100 * np.exp(np.cumsum(rets))
    return close * (1 + np.array(ups)), close * (1 - np.array(downs)), close


PERIODS = st.tuples(st.integers(1, 10), st.integers(1, 30)).map(lambda x: (min(x), max(x)))


@settings(max_examples=200, deadline=None)
@given(data=ohlc(), periods=st.lists(PERIODS, min_size=5, max_size=5))
def test_prop_ripster_clouds_top_ge_bot_for_every_cloud_after_warmup(
    data: tuple[F64, F64, F64], periods: list[tuple[int, int]]
) -> None:
    """TS-IND-143: top >= bot wherever defined; direction and pos stay in their domains."""
    high, low, close = data
    res = ripster_clouds(high, low, close, tuple(periods))
    for c in res.clouds:
        ok = ~np.isnan(c.top)
        assert (c.top[ok] >= c.bot[ok]).all()
        assert np.isin(c.direction[ok], (1.0, -1.0)).all()
        assert np.isin(c.pos[ok], (1.0, 0.0, -1.0)).all()
        assert np.array_equal(ok, ~np.isnan(c.direction))


@settings(max_examples=200, deadline=None)
@given(data=ohlc(), periods=st.lists(PERIODS, min_size=5, max_size=5))
def test_prop_ripster_clouds_stack_nonzero_only_when_5_12_and_34_50_clouds_do_not_overlap(
    data: tuple[F64, F64, F64], periods: list[tuple[int, int]]
) -> None:
    """TS-IND-144: stack is +1 only with c2 fully above c3, -1 only fully below, else 0."""
    high, low, close = data
    res = ripster_clouds(high, low, close, tuple(periods))
    c2, c3, s = res.clouds[1], res.clouds[2], res.stack
    ok = ~np.isnan(s)
    assert np.isin(s[ok], (1.0, 0.0, -1.0)).all()
    assert (c2.bot[s == 1] > c3.top[s == 1]).all()
    assert (c2.top[s == -1] < c3.bot[s == -1]).all()
    overlap = ok & (c2.bot <= c3.top) & (c2.top >= c3.bot)
    assert (s[overlap] == 0).all()
    assert same(s, cloud_stack(c2, c3))
    assert np.isin(res.pullback[ok], (1.0, 0.0, -1.0)).all()
    assert (res.pullback[ok] * s[ok] >= 0).all()  # a pullback never opposes the stack


# --- TS-IND-145 / 146 -----------------------------------------------------------------------


def test_unit_ripster_clouds_registered_with_no_look_ahead_harness() -> None:
    """TS-IND-145: every public Ripster function is registered and passes the section 6 check."""
    bundle = make_bundle(5, 460)
    other = make_bundle(6, 460, sigma=0.08, p_gap=0.5)
    cuts = [260, 330, 459]
    for name in NAMES:
        assert name in reg.REGISTRY, name
        assert check_entry(reg.REGISTRY[name], bundle, cuts, dict.fromkeys(cuts, other)) == []


def test_unit_ripster_clouds_warmup_bars_are_nan_never_zero() -> None:
    """TS-IND-146: below 200 bars the 180/200 cloud is NaN, as are stack and pullback in warm-up."""
    b = make_bundle(9, 199)
    res = ripster_clouds(b.high, b.low, b.close)
    c5 = res.clouds[4]
    for field in ("ema_long", "top", "bot", "direction", "pos"):
        assert np.isnan(getattr(c5, field)).all(), field
    assert np.isnan(c5.ema_short[:179]).all()
    assert not np.isnan(c5.ema_short[179:]).any()
    assert np.isnan(res.stack[:49]).all()  # c3's 50-bar EMA
    assert not np.isnan(res.stack[49:]).any()
    assert np.isnan(res.pullback[:49]).all()
    assert np.isnan(res.clouds[0].pos[:8]).all()  # c1's 9-bar EMA


def test_unit_ripster_clouds_rejects_bad_input() -> None:
    """Mismatched lengths and anything other than five clouds are errors."""
    x = np.ones(10)
    for call in (
        lambda: ripster_clouds(x, x[:9], x),
        lambda: ripster_clouds(x, x, x, ((1, 2),) * 4),
        lambda: ema_cloud(x, x[:9], 1, 2),
    ):
        try:
            call()
        except ValueError:
            continue
        raise AssertionError("expected ValueError")


def test_unit_ripster_tv_export_parse_both_column_variants() -> None:
    """The parity parser reads EMAs named by period, or the ten short / long plots in order."""
    periods = (8, 9, 5, 12, 34, 50, 72, 89, 180, 200)
    named = "time,open,high,low,close," + ",".join(f"EMA {k}" for k in periods)
    plots = "time,open,high,low,close," + ",".join(["Short Source", "Long Source"] * 5)
    row = "1,1,2,0.5,1.5," + ",".join(str(float(k)) for k in periods)
    for head in (named, plots):
        export = parse_ripster_export(f"{head}\n{row}\n")
        assert export is not None
        assert {k: float(v[0]) for k, v in export.emas.items()} == {k: float(k) for k in periods}
        assert (export.high[0], export.low[0], export.close[0]) == (2.0, 0.5, 1.5)
    assert parse_ripster_export("time,open,high,low,close,Up Trend\n1,1,2,0.5,1.5,1\n") is None
    try:
        parse_ripster_export("time,high,low,close,EMA 8\n1,2,0.5,1.5,1\n")
    except ValueError:
        return
    raise AssertionError("expected ValueError for a partial Ripster export")
