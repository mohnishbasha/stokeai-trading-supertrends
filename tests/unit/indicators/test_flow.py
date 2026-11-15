# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Estimated order flow (TS-IND-123 to TS-IND-129, 131, 132 and extras TS-IND-235 to TS-IND-238).

`bar_start` values are session-local (America/New_York) wall-clock datetime64[m]; the caller
converts. Expected values are worked by hand in the comments.
"""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from supertrends.indicators import flow as f

TOL = 1e-12
N_SESS = 10
_DAYS = np.arange(np.datetime64("2026-03-02"), np.datetime64("2026-03-02") + 30, dtype="datetime64[D]")
# Weekdays only: 1970-01-01 was a Thursday, so (days + 3) % 7 is 0 for Monday .. 4 for Friday.
SESSIONS = _DAYS[(_DAYS.astype("int64") + 3) % 7 < 5][:12]


def _arr(x: list[float]) -> NDArray[np.float64]:
    return np.array(x, dtype=np.float64)


def _world(
    n_sessions: int = N_SESS, intraday: set[int] | None = None
) -> tuple[NDArray[np.datetime64], dict[str, NDArray[np.float64]], dict[str, NDArray[np.generic]]]:
    """Daily bars closing at the high (daily pct = 1) and one 09:30 bar per intraday session.

    Session k (0-based) has a single bar with range 8..10, volume 100 and close 8 + 2*f_k where
    f_k = (k + 1) / 20, so buy = 100 * f_k and delta_pct = 2 * f_k - 1 = (k + 1) / 10 - 1.
    """
    sess = SESSIONS[:n_sessions]
    daily = {
        "d_high": np.full(n_sessions, 10.0),
        "d_low": np.full(n_sessions, 8.0),
        "d_close": np.full(n_sessions, 10.0),
        "d_volume": np.full(n_sessions, 1000.0),
    }
    keep = sorted(range(n_sessions) if intraday is None else intraday)
    start = np.array([sess[k].astype("datetime64[m]") + 570 for k in keep], dtype="datetime64[m]")
    intra: dict[str, NDArray[np.generic]] = {
        "bar_start": start,
        "high": np.full(len(keep), 10.0),
        "low": np.full(len(keep), 8.0),
        "close": _arr([8.0 + 2.0 * (k + 1) / 20.0 for k in keep]),
        "volume": np.full(len(keep), 100.0),
    }
    return sess, daily, intra


@given(
    low=st.lists(st.floats(1.0, 500.0), min_size=1, max_size=40),
    spread=st.lists(st.floats(0.0, 20.0), min_size=40, max_size=40),
    frac=st.lists(st.floats(0.0, 1.0), min_size=40, max_size=40),
    vol=st.lists(st.floats(0.0, 1e9), min_size=40, max_size=40),
    prev=st.lists(st.floats(1.0, 500.0), min_size=40, max_size=40),
)
def test_ts_ind_123_buy_plus_sell_equals_volume_for_every_bar(
    low: list[float],
    spread: list[float],
    frac: list[float],
    vol: list[float],
    prev: list[float],
) -> None:
    """TS-IND-123: buy + sell == volume, both non-negative, for every bar (property)."""
    n = len(low)
    lo = _arr(low)
    hi = lo + _arr(spread[:n])
    cl = np.minimum(hi, np.maximum(lo, lo + (hi - lo) * _arr(frac[:n])))
    volume = _arr(vol[:n])
    buy, sell = f.split_volume(hi, lo, cl, volume, _arr(prev[:n]))
    assert np.allclose(buy + sell, volume, rtol=1e-12, atol=0.0)
    assert (buy >= 0).all()
    assert (sell >= 0).all()


def test_ts_ind_124_zero_range_bar_close_ge_prev_close_all_buy() -> None:
    """TS-IND-124: zero range with close >= prev_close (up and equal) is all buy."""
    hi = lo = cl = _arr([10.0, 10.0])
    buy, sell = f.split_volume(hi, lo, cl, _arr([100.0, 50.0]), _arr([9.0, 10.0]))
    assert buy.tolist() == [100.0, 50.0]
    assert sell.tolist() == [0.0, 0.0]


def test_ts_ind_125_zero_range_bar_close_lt_prev_close_all_sell() -> None:
    """TS-IND-125: zero range with close < prev_close is all sell."""
    hi = lo = cl = _arr([10.0])
    buy, sell = f.split_volume(hi, lo, cl, _arr([100.0]), _arr([11.0]))
    assert buy.tolist() == [0.0]
    assert sell.tolist() == [100.0]


def test_ts_ind_126_daily_delta_and_delta_pct_from_5m_bars() -> None:
    """TS-IND-126: daily delta and delta percent from 5-minute bars.

    Hand derivation, session 0:
      bar1 h10 l8 c9.5 v100: buy 75, sell 25.
      bar2 h10 l10 c10 v50 zero range, prev close 9.5: buy 50.
      buy 125, sell 25, delta 100, volume 150, pct 2/3.
    Session 1:
      bar1 h5 l5 c5 v40 zero range, prev close 10 (carried over from session 0): sell 40.
      bar2 h6 l4 c4.5 v80: buy 20, sell 60.
      buy 20, sell 100, delta -80, volume 120, pct -2/3.
    Sessions 2..9: one flat bar at 4.5 each, equal to the previous close: all buy, pct 1.
    """
    sess = SESSIONS[:N_SESS]
    t0 = sess[0].astype("datetime64[m]") + 570
    t1 = sess[1].astype("datetime64[m]") + 570
    rest = np.array([s.astype("datetime64[m]") + 570 for s in sess[2:]], dtype="datetime64[m]")
    bar_start = np.concatenate([np.array([t0, t0 + 5, t1, t1 + 5], dtype="datetime64[m]"), rest])
    k = len(rest)
    hi = np.concatenate([_arr([10, 10, 5, 6]), np.full(k, 4.5)])
    lo = np.concatenate([_arr([8, 10, 5, 4]), np.full(k, 4.5)])
    cl = np.concatenate([_arr([9.5, 10, 5, 4.5]), np.full(k, 4.5)])
    vol = np.concatenate([_arr([100, 50, 40, 80]), np.full(k, 10.0)])
    ones = np.full(N_SESS, 10.0)
    res = f.estimate_order_flow(sess, ones, ones, ones, ones, bar_start, hi, lo, cl, vol)
    assert res.quality is f.FlowQuality.INTRADAY
    assert res.buy[0] == pytest.approx(125.0)
    assert res.sell[0] == pytest.approx(25.0)
    assert res.delta[0] == pytest.approx(100.0)
    assert res.delta_pct[0] == pytest.approx(2.0 / 3.0)
    assert res.buy[1] == pytest.approx(20.0)
    assert res.sell[1] == pytest.approx(100.0)
    assert res.delta[1] == pytest.approx(-80.0)
    assert res.delta_pct[1] == pytest.approx(-2.0 / 3.0)
    assert res.delta_pct[5] == pytest.approx(1.0)


def test_ts_ind_127_delta_pct_10_is_mean_of_last_10_sessions() -> None:
    """TS-IND-127: mean over the last 10 sessions.

    Hand derivation: pct_k = (k + 1) / 10 - 1 (see `_world`). For k = 0..9 the mean of (k + 1) is
    5.5, so the mean pct is 0.55 - 1 = -0.45. With 12 sessions only k = 2..11 count: the mean of
    (k + 1) is 7.5, so the mean pct is 0.75 - 1 = -0.25.
    """
    sess, daily, intra = _world()
    res = f.estimate_order_flow(sess, **daily, **intra)  # type: ignore[arg-type]
    assert res.delta_pct_10 == pytest.approx(-0.45, abs=TOL)
    sess12, daily12, intra12 = _world(12)
    res12 = f.estimate_order_flow(sess12, **daily12, **intra12)  # type: ignore[arg-type]
    assert res12.delta_pct_10 == pytest.approx(-0.25, abs=TOL)


@pytest.mark.parametrize(
    ("missing", "quality", "expected"),
    [
        ({0, 1}, f.FlowQuality.INTRADAY, -0.35),  # 8 of 10: mean (k+1), k=2..9 is 6.5 -> -0.35
        ({0, 1, 2}, f.FlowQuality.DAILY_ESTIMATE, 1.0),  # 7 of 10: daily bars close at the high
        (set(), f.FlowQuality.INTRADAY, -0.45),
    ],
)
def test_ts_ind_128_quality_intraday_needs_8_of_10_sessions(
    missing: set[int], quality: f.FlowQuality, expected: float
) -> None:
    """TS-IND-128: 8 of 10 sessions is intraday, 7 of 10 falls back to daily_estimate."""
    sess, daily, intra = _world(intraday=set(range(N_SESS)) - missing)
    res = f.estimate_order_flow(sess, **daily, **intra)  # type: ignore[arg-type]
    assert res.quality is quality
    assert res.delta_pct_10 == pytest.approx(expected, abs=TOL)
    assert res.intraday_sessions == N_SESS - len(missing)


def test_ts_ind_129_daily_estimate_when_intraday_missing_and_flagged() -> None:
    """TS-IND-129: no 5m bars -> daily_estimate, flagged; the daily split is used."""
    sess, daily, _ = _world()
    res = f.estimate_order_flow(sess, **daily)
    assert res.quality is f.FlowQuality.DAILY_ESTIMATE
    assert res.daily_fallback is True
    assert res.intraday_sessions == 0
    # Daily bars close at the high: buy = volume, sell = 0, pct = 1 every session.
    assert res.delta_pct_10 == pytest.approx(1.0)
    assert res.buy[0] == pytest.approx(1000.0)
    # Empty intraday arrays behave the same as None.
    empty = np.array([], dtype="datetime64[m]")
    e = np.array([], dtype=np.float64)
    res2 = f.estimate_order_flow(sess, **daily, bar_start=empty, high=e, low=e, close=e, volume=e)
    assert res2.daily_fallback is True
    # Intraday quality is not flagged as a fallback.
    sess, daily, intra = _world()
    ok = f.estimate_order_flow(sess, **daily, **intra)  # type: ignore[arg-type]
    assert ok.daily_fallback is False


class _Fake:
    def __init__(self, covered: int) -> None:
        self.covered = covered

    def delta_pct(self, sessions: NDArray[np.datetime64]) -> NDArray[np.float64]:
        out = np.full(len(sessions), np.nan)
        out[len(sessions) - self.covered :] = 0.25
        return out


def test_ts_ind_131_trades_classifier_accepted_by_interface() -> None:
    """TS-IND-131: a tick-rule classifier plugs in and yields quality `trades`."""
    sess, daily, intra = _world()
    res = f.estimate_order_flow(sess, **daily, **intra, trades=_Fake(10))  # type: ignore[arg-type]
    assert res.quality is f.FlowQuality.TRADES
    assert res.delta_pct_10 == pytest.approx(0.25)
    assert res.daily_fallback is False
    assert f.FlowQuality("trades") is f.FlowQuality.TRADES
    # Too little trade coverage: falls through to intraday.
    low = f.estimate_order_flow(sess, **daily, **intra, trades=_Fake(5))  # type: ignore[arg-type]
    assert low.quality is f.FlowQuality.INTRADAY


def test_ts_ind_132_regular_session_only() -> None:
    """TS-IND-132: bars starting before 09:30 or at or after 16:00 are ignored.

    One session, bars: 09:25 (ignored), 09:30 h10 l8 c10 v100 (buy 100), 15:55 h10 l8 c8 v100
    (sell 100), 16:00 (ignored), 18:00 (ignored). delta = 0, pct = 0.
    """
    sess = SESSIONS[:1]
    day = sess[0].astype("datetime64[m]")
    bar_start = np.array([day + 565, day + 570, day + 955, day + 960, day + 1080])
    hi = np.full(5, 10.0)
    lo = np.full(5, 8.0)
    cl = _arr([8.0, 10.0, 8.0, 10.0, 10.0])
    vol = np.full(5, 100.0)
    one = np.full(1, 10.0)
    res = f.estimate_order_flow(
        sess, one, one, one, one, bar_start, hi, lo, cl, vol, min_intraday_sessions=1
    )
    assert res.quality is f.FlowQuality.INTRADAY
    assert res.buy[0] == pytest.approx(100.0)
    assert res.sell[0] == pytest.approx(100.0)
    assert res.delta_pct[0] == pytest.approx(0.0)


def test_ts_ind_235_daily_path_uses_prior_daily_close_and_first_bar_is_buy() -> None:
    """TS-IND-235: A-07: daily zero-range bars compare to the prior daily close.

    Day 0 flat (h=l=c=10): no prior close, treated as close >= prev: buy.
    Day 1 flat at 9 (prior close 10): sell. Day 2 flat at 9 (equal): buy.
    """
    sess = SESSIONS[:3]
    c = _arr([10.0, 9.0, 9.0])
    vol = _arr([100.0, 100.0, 100.0])
    res = f.estimate_order_flow(sess, c, c, c, vol)
    assert res.delta_pct.tolist() == [1.0, -1.0, 1.0]
    assert np.isnan(res.delta_pct_10)  # fewer than 10 daily sessions on the daily path


def test_ts_ind_236_zero_volume_session_is_nan_and_excluded_from_mean() -> None:
    """TS-IND-236: a zero-volume session has delta_pct NaN and is left out of the mean."""
    sess, daily, _ = _world()
    daily["d_volume"][4] = 0.0
    res = f.estimate_order_flow(sess, **daily)
    assert np.isnan(res.delta_pct[4])
    assert res.delta_pct_10 == pytest.approx(1.0)


def test_ts_ind_237_missing_sessions_older_than_window_do_not_matter() -> None:
    """TS-IND-237: only the last 10 sessions count for the 8-of-10 test."""
    sess, daily, intra = _world(12, set(range(2, 12)))
    res = f.estimate_order_flow(sess, **daily, **intra)  # type: ignore[arg-type]
    assert res.quality is f.FlowQuality.INTRADAY
    assert res.intraday_sessions == 10


def test_ts_ind_238_unsorted_or_mismatched_inputs_raise() -> None:
    """TS-IND-238: unsorted bar times and length mismatches raise ValueError."""
    sess, daily, intra = _world()
    bad = {k: x[::-1] for k, x in intra.items()}
    with pytest.raises(ValueError, match="sorted"):
        f.estimate_order_flow(sess, **daily, **bad)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="length"):
        f.estimate_order_flow(
            sess, daily["d_high"][:3], daily["d_low"], daily["d_close"], daily["d_volume"]
        )
    with pytest.raises(ValueError, match="length"):
        f.split_volume(_arr([1.0]), _arr([1.0, 2.0]), _arr([1.0]), _arr([1.0]), _arr([1.0]))
    partial = {"bar_start": intra["bar_start"], "high": intra["high"]}
    with pytest.raises(ValueError, match="together"):
        f.estimate_order_flow(sess, **daily, **partial)  # type: ignore[arg-type]
