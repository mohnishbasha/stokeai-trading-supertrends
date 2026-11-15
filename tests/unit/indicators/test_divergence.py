# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Divergence detector (TS-IND-070 to TS-IND-080, TS-IND-200 to TS-IND-208).

Fixtures are constructed by hand: a flat low of 10 (high 11) with single-bar dips (pivot lows)
or spikes (pivot highs), and an oscillator of 50 with chosen values at the pivot bars. A flat bar
is never a strict pivot, so the only pivots are the ones placed. With width 5 a pivot at p is
confirmed at p + 5.
"""

import dataclasses
import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from supertrends import indicators
from supertrends.indicators import divergence as dv
from supertrends.indicators.primitives import ema, obv, resample_weekly, rsi

F = NDArray[np.float64]


def build(
    n: int,
    dips: dict[int, float] | None = None,
    spikes: dict[int, float] | None = None,
    osc_at: dict[int, float] | None = None,
) -> tuple[F, F, F]:
    low = np.full(n, 10.0)
    high = np.full(n, 11.0)
    osc = np.full(n, 50.0)
    for p, v in (dips or {}).items():
        low[p] = v
        high[p] = v + 1.0
    for p, v in (spikes or {}).items():
        high[p] = v
    for p, v in (osc_at or {}).items():
        osc[p] = v
    return high, low, osc


def detect(high: F, low: F, osc: F, **kw: object) -> list[dv.Divergence]:
    return dv.detect_divergences(high, low, osc, oscillator="rsi", **kw)  # type: ignore[arg-type]


def test_regular_bullish_found() -> None:
    """TS-IND-070: price lower low (9 -> 8), oscillator higher low (30 -> 35)."""
    high, low, osc = build(30, dips={10: 9.0, 18: 8.0}, osc_at={10: 30.0, 18: 35.0})
    (rec,) = detect(high, low, osc)
    assert (rec.kind, rec.side) == ("regular", "bullish")
    assert (rec.p1, rec.p2, rec.price1, rec.price2, rec.osc1, rec.osc2) == (
        10,
        18,
        9.0,
        8.0,
        30.0,
        35.0,
    )


def test_regular_bearish_found() -> None:
    """TS-IND-071: price higher high (14 -> 15), oscillator lower high (70 -> 65)."""
    high, low, osc = build(30, spikes={10: 14.0, 18: 15.0}, osc_at={10: 70.0, 18: 65.0})
    (rec,) = detect(high, low, osc)
    assert (rec.kind, rec.side) == ("regular", "bearish")
    assert (rec.price1, rec.price2, rec.osc1, rec.osc2) == (14.0, 15.0, 70.0, 65.0)


def test_hidden_bullish_found() -> None:
    """TS-IND-072: price higher low (8 -> 9), oscillator lower low (35 -> 30)."""
    high, low, osc = build(30, dips={10: 8.0, 18: 9.0}, osc_at={10: 35.0, 18: 30.0})
    (rec,) = detect(high, low, osc)
    assert (rec.kind, rec.side) == ("hidden", "bullish")


def test_hidden_bearish_found() -> None:
    """TS-IND-073: price lower high (15 -> 14), oscillator higher high (65 -> 70)."""
    high, low, osc = build(30, spikes={10: 15.0, 18: 14.0}, osc_at={10: 65.0, 18: 70.0})
    (rec,) = detect(high, low, osc)
    assert (rec.kind, rec.side) == ("hidden", "bearish")


def test_unconfirmed_second_pivot_not_reported() -> None:
    """TS-IND-074: second pivot at 18 is confirmed at 23; before that nothing is reported."""
    # Truncated input: last index 21, the dip at 18 has only 3 bars after it.
    high, low, osc = build(30, dips={10: 9.0, 18: 8.0}, osc_at={10: 30.0, 18: 35.0})
    assert detect(high[:22], low[:22], osc[:22]) == []
    assert detect(high[:23], low[:23], osc[:23]) == []  # last index 22: still 1 short
    assert len(detect(high[:24], low[:24], osc[:24])) == 1  # last index 23 = 18 + 5
    # as_of on the full arrays behaves identically.
    assert detect(high, low, osc, as_of=22) == []
    assert detect(high, low, osc, as_of=23)[0].confirmed_at == 23


def test_monotonic_series_no_false_detection() -> None:
    """TS-IND-075: strictly rising and strictly falling series have no pivots."""
    x = np.arange(1.0, 101.0)
    for h, lo, o in ((x + 1, x, x), (x[::-1] + 1, x[::-1], x[::-1])):
        assert detect(h, lo, o) == []
        assert dv.divergence_records(h, lo, o, oscillator="rsi") == []
        assert dv.detect_all_divergences(h, lo, lo, np.ones(100)) == []


def test_second_pivot_older_than_15_bars_excluded() -> None:
    """TS-IND-076: second pivot at 18; t - p2 <= 15 counts, 16 does not (pivot-bar distance)."""
    high, low, osc = build(60, dips={10: 9.0, 18: 8.0}, osc_at={10: 30.0, 18: 35.0})
    assert len(detect(high, low, osc, as_of=33)) == 1  # 33 - 18 = 15
    assert detect(high, low, osc, as_of=34) == []  # 34 - 18 = 16
    assert detect(high[:35], low[:35], osc[:35]) == []


def test_pivots_outside_60_bar_lookback_excluded() -> None:
    """TS-IND-077: p1 = 10, p2 = 62. The last 60 bars at t are t-59..t, so t = 69 is the last."""
    high, low, osc = build(80, dips={10: 9.0, 62: 8.0}, osc_at={10: 30.0, 62: 35.0})
    assert detect(high, low, osc, as_of=66) == []  # not confirmed (62 + 5 = 67)
    assert len(detect(high, low, osc, as_of=67)) == 1
    assert len(detect(high, low, osc, as_of=69)) == 1  # 69 - 10 = 59
    assert detect(high, low, osc, as_of=70) == []  # 70 - 10 = 60, p1 left the window


def test_each_oscillator_reported_separately() -> None:
    """TS-IND-078: records carry their oscillator name; no merging across oscillators."""
    high, low, _ = build(30, dips={10: 9.0, 18: 8.0})
    rsi_v = build(30, osc_at={10: 30.0, 18: 35.0})[2]  # regular bullish
    macd_v = build(30, osc_at={10: 1.0, 18: 0.5})[2]  # price LL and osc LL: none
    obv_v = build(30, osc_at={10: 5.0, 18: 6.0})[2]  # regular bullish
    found = {
        name: dv.detect_divergences(high, low, v, oscillator=name)
        for name, v in (("rsi", rsi_v), ("macd_hist", macd_v), ("obv", obv_v))
    }
    assert [r.oscillator for r in found["rsi"]] == ["rsi"]
    assert found["macd_hist"] == []
    assert [r.oscillator for r in found["obv"]] == ["obv"]
    assert found["rsi"][0].osc2 == 35.0
    assert found["obv"][0].osc2 == 6.0


def _walk(seed: int = 0, n: int = 300) -> tuple[F, F, F, F]:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0.1, 1, n)
    low = close - rng.uniform(0.1, 1, n)
    volume = rng.uniform(1e5, 2e5, n)
    return high, low, close, volume


def test_detect_all_reports_rsi_macd_hist_obv_from_primitives() -> None:
    """TS-IND-078: the convenience computes RSI(14), MACD hist, and OBV and tags each record."""
    high, low, close, volume = _walk()
    expected = {"rsi": rsi(close, 14), "obv": obv(close, volume)}
    seen: set[str] = set()
    for t in range(len(close)):
        for rec in dv.detect_all_divergences(high, low, close, volume, as_of=t):
            seen.add(rec.oscillator)
            assert rec.timeframe == "daily"
            assert rec.confirmed_at == rec.p2 + 5 <= t
            if rec.oscillator in expected:
                assert rec.osc1 == expected[rec.oscillator][rec.p1]
                assert rec.osc2 == expected[rec.oscillator][rec.p2]
    assert seen == {"rsi", "macd_hist", "obv"}


def test_weekly_uses_pivot_width_3() -> None:
    """TS-IND-079: width 3 confirms at p + 3; the same dips are unconfirmed with width 5."""
    high, low, osc = build(20, dips={8: 9.0, 14: 8.0}, osc_at={8: 30.0, 14: 35.0})
    assert detect(high[:17], low[:17], osc[:17], width=3, timeframe="weekly") == []
    (rec,) = detect(high[:18], low[:18], osc[:18], width=3, timeframe="weekly")
    assert (rec.confirmed_at, rec.timeframe) == (17, "weekly")
    assert detect(high[:18], low[:18], osc[:18], width=5) == []


def test_weekly_on_resampled_bars() -> None:
    """TS-IND-079: weekly detection runs on `resample_weekly` bars, width 3, week indexes."""
    high, low, close, volume = _walk()
    dates = np.datetime64("2020-01-06") + 7 * np.arange(len(close))  # one Monday per week
    weekly = resample_weekly(dates.astype("datetime64[D]"), close, high, low, close, volume)
    recs = dv.detect_weekly_divergences(weekly, as_of=None)
    all_recs: list[dv.Divergence] = []
    for t in range(len(close)):
        all_recs += dv.detect_weekly_divergences(weekly, as_of=t)
    assert all_recs
    assert {r.timeframe for r in all_recs} == {"weekly"}
    assert all(r.confirmed_at == r.p2 + 3 for r in all_recs)
    assert {r.oscillator for r in all_recs} == {"rsi", "macd_hist", "obv"}
    assert all(r.confirmed_at <= len(close) - 1 for r in recs)


def test_record_shape() -> None:
    """TS-IND-080: typed frozen record with kind, side, oscillator, timeframe, both pivots."""
    high, low, osc = build(30, dips={10: 9.0, 18: 8.0}, osc_at={10: 30.0, 18: 35.0})
    (rec,) = detect(high, low, osc)
    assert [f.name for f in dataclasses.fields(rec)] == [
        "kind",
        "side",
        "oscillator",
        "timeframe",
        "p1",
        "p2",
        "price1",
        "price2",
        "osc1",
        "osc2",
        "confirmed_at",
    ]
    assert rec == dv.Divergence(
        "regular", "bullish", "rsi", "daily", 10, 18, 9.0, 8.0, 30.0, 35.0, 23
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.p1 = 0  # type: ignore[misc]


def test_newer_pivot_supersedes_second_pivot() -> None:
    """TS-IND-200: only the two most recent pivots compare; a third pivot replaces p2."""
    # Dips 10 (9, osc 30), 18 (8, osc 35): regular bullish, active 23..25. Dip 20 would be
    # inside the 5-bar side of 18, so use 26 (10 - 1 = 9.5, osc 20): vs 18 price HL, osc LL.
    high, low, osc = build(
        40, dips={10: 9.0, 18: 8.0, 26: 9.5}, osc_at={10: 30.0, 18: 35.0, 26: 20.0}
    )
    assert [r.p2 for r in detect(high, low, osc, as_of=25)] == [18]
    (hidden,) = detect(high, low, osc, as_of=31)  # 26 confirmed at 31
    assert (hidden.kind, hidden.p1, hidden.p2) == ("hidden", 18, 26)
    assert [r.p2 for r in detect(high, low, osc, as_of=30)] == [18]


def test_macd_hist_matches_independent_loop() -> None:
    """TS-IND-201: private MACD histogram equals a plain-Python EMA12-EMA26 minus EMA9 loop."""
    _, _, close, _ = _walk(3, 120)

    def ema_loop(x: list[float], n: int) -> list[float]:
        out = [math.nan] * len(x)
        k = 2.0 / (n + 1)
        out[n - 1] = sum(x[:n]) / n  # SMA seed
        for i in range(n, len(x)):
            out[i] = x[i] * k + out[i - 1] * (1 - k)
        return out

    xs = close.tolist()
    e12, e26 = ema_loop(xs, 12), ema_loop(xs, 26)
    line = [a - b for a, b in zip(e12[25:], e26[25:], strict=True)]
    signal = ema_loop(line, 9)
    expected = [math.nan] * 25 + [a - b for a, b in zip(line, signal, strict=True)]
    got = dv._macd_hist(close)
    assert np.allclose(got, expected, equal_nan=True, atol=1e-9)
    assert np.isnan(got[: 25 + 8]).all()
    assert np.isnan(dv._macd_hist(close[:20])).all()
    # Sanity: uses the same primitive.
    assert np.allclose(ema(close, 12)[30], e12[30])


def test_nan_oscillator_and_equal_values_are_not_divergences() -> None:
    """TS-IND-202: NaN oscillator at a pivot, equal prices, or equal oscillator values: none."""
    high, low, osc = build(30, dips={10: 9.0, 18: 8.0}, osc_at={10: math.nan, 18: 35.0})
    assert detect(high, low, osc) == []
    high, low, osc = build(30, dips={10: 8.0, 18: 8.0}, osc_at={10: 30.0, 18: 35.0})
    assert detect(high, low, osc) == []
    high, low, osc = build(30, dips={10: 9.0, 18: 8.0}, osc_at={10: 30.0, 18: 30.0})
    assert detect(high, low, osc) == []


def test_lows_and_highs_compared_separately() -> None:
    """TS-IND-203: a bullish pivot-low pair and a bearish pivot-high pair are both reported."""
    high, low, osc = build(
        30,
        dips={10: 9.0, 18: 8.0},
        spikes={12: 14.0, 20: 15.0},
        osc_at={10: 30.0, 18: 35.0, 12: 70.0, 20: 65.0},
    )
    recs = detect(high, low, osc)
    assert sorted((r.kind, r.side) for r in recs) == [
        ("regular", "bearish"),
        ("regular", "bullish"),
    ]


def test_invalid_inputs_and_empty() -> None:
    """TS-IND-204: mismatched lengths and width < 1 raise; empty input and bad as_of give []."""
    a = np.ones(10)
    with pytest.raises(ValueError, match="same length"):
        detect(a, a, np.ones(9))
    with pytest.raises(ValueError, match="width"):
        detect(a, a, a, width=0)
    empty = np.zeros(0)
    assert detect(empty, empty, empty) == []
    assert detect(a, a, a, as_of=10) == []
    assert detect(a, a, a, as_of=-1) == []


def test_series_matches_detect_each_bar() -> None:
    """TS-IND-205: divergence_series flag at t equals detect_divergences(as_of=t)."""
    high, low, close, _ = _walk(1, 200)
    osc = rsi(close, 14)
    series = dv.divergence_series(high, low, osc)
    for t in range(len(close)):
        found = {(r.kind, r.side) for r in detect(high, low, osc, as_of=t)}
        assert series.regular_bullish[t] == (("regular", "bullish") in found)
        assert series.regular_bearish[t] == (("regular", "bearish") in found)
        assert series.hidden_bullish[t] == (("hidden", "bullish") in found)
        assert series.hidden_bearish[t] == (("hidden", "bearish") in found)
    assert series.regular_bullish.any()
    assert series.hidden_bearish.any()


def test_records_sorted_with_confirmed_at() -> None:
    """TS-IND-206: divergence_records lists every record sorted by confirmed_at = p2 + width."""
    high, low, close, _ = _walk(2, 250)
    recs = dv.divergence_records(high, low, rsi(close, 14), oscillator="rsi")
    assert len(recs) > 3
    assert [r.confirmed_at for r in recs] == sorted(r.confirmed_at for r in recs)
    assert all(r.confirmed_at == r.p2 + 5 and r.p1 < r.p2 for r in recs)


def test_aggregation_exports() -> None:
    """TS-IND-207: the module `__all__` is re-exported by `supertrends.indicators`."""
    assert set(dv.__all__) <= set(indicators.__all__)
    assert "detect_divergences" in indicators.__all__


@settings(max_examples=60, deadline=None)
@given(
    steps=st.lists(st.floats(-2, 2, allow_nan=False), min_size=1, max_size=120),
    osc_steps=st.lists(st.floats(-2, 2, allow_nan=False), min_size=120, max_size=120),
    width=st.sampled_from([3, 5]),
    cut=st.integers(0, 119),
)
def test_no_look_ahead_property(
    steps: list[float], osc_steps: list[float], width: int, cut: int
) -> None:
    """TS-IND-208: no record has p2 + width > last index; truncating the input changes nothing."""
    n = len(steps)
    close = 100 + np.cumsum(np.array(steps))
    high, low = close + 0.5, close - 0.5
    osc = np.cumsum(np.array(osc_steps[:n]))
    t = min(cut, n - 1)
    truncated = detect(high[: t + 1], low[: t + 1], osc[: t + 1], width=width)
    assert all(r.p2 + width <= t for r in truncated)
    assert truncated == detect(high, low, osc, width=width, as_of=t)
    series = dv.divergence_series(high, low, osc, width=width)
    cut_series = dv.divergence_series(high[: t + 1], low[: t + 1], osc[: t + 1], width=width)
    assert np.array_equal(series.regular_bullish[: t + 1], cut_series.regular_bullish)
    assert np.array_equal(series.hidden_bearish[: t + 1], cut_series.hidden_bearish)


def test_pivots_too_far_apart_never_active() -> None:
    """TS-IND-209: p1 = 10, p2 = 70 are 60 apart; p1 leaves the window before p2 confirms."""
    high, low, osc = build(90, dips={10: 9.0, 70: 8.0}, osc_at={10: 30.0, 70: 35.0})
    assert dv.divergence_records(high, low, osc, oscillator="rsi") == []
    assert all(detect(high, low, osc, as_of=t) == [] for t in range(90))
