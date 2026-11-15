# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""No-look-ahead harness (TS-IND-090 to 092, 097 to 099, 247; TEST_PLAN section 6).

Every public indicator in `supertrends.indicators.__all__` is in the registry. The property test
runs each registered entry on hypothesis-generated bundles of 300 to 700 sessions (see
`lookahead_support`), at the cuts 250, N-6, N-1 and one sampled cut, and checks truncation and
perturbation invariance. Cost: one bundle per example, five-ish computations per entry; the
`dev` profile (15 examples) keeps the whole file well under a minute, `ci` runs 100 examples.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from supertrends import indicators
from supertrends.indicators import registry as reg
from supertrends.indicators.divergence import detect_weekly_divergences
from supertrends.indicators.primitives import pivots, resample_weekly
from supertrends.indicators.registry import Bundle, Entry
from tests.unit.indicators.lookahead_support import (
    FIXED_FIRST_CUT,
    bundles,
    check_entry,
    make_bundle,
)


def _cuts(n: int, sampled: int) -> list[int]:
    return sorted({FIXED_FIRST_CUT, n - 6, n - 1, sampled})


@given(bundles(), st.data())
def test_prop_indicators_all_truncation_does_not_change_past_values(
    bundle: Bundle, data: st.DataObject
) -> None:
    """TS-IND-090: truncation and perturbation invariance for every registered indicator."""
    assert len(reg.REGISTRY) >= 50
    n = len(bundle)
    cuts = _cuts(n, data.draw(st.integers(FIXED_FIRST_CUT, n - 1)))
    other = make_bundle(data.draw(st.integers(0, 2**32 - 1)), n, sigma=0.08, p_gap=0.5)
    others = dict.fromkeys((cuts[1], cuts[-1]), other)
    problems: list[str] = []
    for entry in reg.REGISTRY.values():
        problems += check_entry(entry, bundle, cuts, others)
    assert problems == []


def _public_functions() -> list[str]:
    return [n for n in indicators.__all__ if inspect.isfunction(getattr(indicators, n))]


def test_unit_indicators_registry_missing_public_function_fails_test() -> None:
    """TS-IND-091: every name in `__all__` is registered or explicitly exempt, and not both."""
    assert reg.unregistered() == []
    assert set(reg.REGISTRY).isdisjoint(reg.EXEMPT)
    assert set(_public_functions()) <= set(reg.REGISTRY)
    assert "supertrend" in indicators.__all__


def test_unit_indicators_registry_check_fails_for_a_new_public_function(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-IND-091: adding a public function without registering it makes the check fail."""

    def fresh_indicator(x: np.ndarray) -> np.ndarray:
        return x

    monkeypatch.setattr(indicators, "fresh_indicator", fresh_indicator, raising=False)
    monkeypatch.setattr(indicators, "__all__", [*indicators.__all__, "fresh_indicator"])
    assert reg.unregistered() == ["fresh_indicator"]


def test_unit_indicators_registry_exemptions_are_not_plain_functions() -> None:
    """TS-IND-247: exempt names exist in `__all__`, carry a reason, and are not functions."""
    for name, reason in reg.EXEMPT.items():
        assert name in indicators.__all__
        assert reason.strip()
        assert not inspect.isfunction(getattr(indicators, name))


def _leaky_centered_ma(b: Bundle) -> dict[str, np.ndarray]:
    """Centered 3-bar moving average: x[t+1] leaks into t."""
    c = b.close
    out = np.full(len(c), np.nan)
    out[1:-1] = (c[:-2] + c[1:-1] + c[2:]) / 3.0
    return {"out": out}


def _leaky_next_close(b: Bundle) -> dict[str, np.ndarray]:
    out = np.full(len(b), np.nan)
    out[:-1] = b.close[1:]
    return {"out": out}


def _leaky_asof(b: Bundle, t: int) -> object:
    """Ignores the as-of bar and reads the last bar it was given."""
    return float(b.close[-1])


@pytest.mark.parametrize(
    "entry",
    [
        Entry("leaky_centered_ma", series=_leaky_centered_ma),
        Entry("leaky_next_close", series=_leaky_next_close),
        Entry("leaky_asof", asof=_leaky_asof),
    ],
    ids=lambda e: e.name,
)
def test_prop_indicators_leaky_negative_control_is_detected(entry: Entry) -> None:
    """TS-IND-092: the harness flags an injected leaky indicator."""
    bundle = make_bundle(7, 400)
    other = make_bundle(8, 400, sigma=0.08)
    found = check_entry(entry, bundle, [250, 394, 399], {394: other})
    assert found, f"{entry.name} was not flagged"


def test_prop_indicators_real_indicator_made_leaky_is_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-IND-092: patching a registered indicator to look ahead is flagged through the registry."""

    def leaky_sma(x: np.ndarray, n: int) -> np.ndarray:
        out = np.full(len(x), np.nan)
        out[: len(x) - 1] = x[1:]
        return out

    monkeypatch.setattr(reg, "sma", leaky_sma)
    bundle = make_bundle(3, 400)
    found = check_entry(reg.REGISTRY["sma"], bundle, [250, 399], {399: make_bundle(4, 400)})
    assert found


def test_unit_indicators_series_outputs_match_input_length_and_warm_up_is_nan() -> None:
    """TS-IND-097: series outputs have the input length and start with NaN where warm-up applies."""
    bundle = make_bundle(11, 400)
    warm = {"sma": 19, "ema": 19, "rma": 13, "atr": 13, "rsi": 14, "bbw_rank": 125, "zscore": 19}
    for name, entry in reg.REGISTRY.items():
        if entry.series is None:
            continue
        for key, values in entry.series(bundle).items():
            assert values.dtype == np.float64, f"{name}.{key}"
            assert values.shape == (400,), f"{name}.{key}"
        if name in warm:
            out = next(iter(entry.series(bundle).values()))
            assert np.isnan(out[: warm[name]]).all(), name
            assert not np.isnan(out[400 - 1]), name


@given(bundles(max_len=400), st.integers(1, 3))
def test_prop_pivots_confirm_width_bars_late(bundle: Bundle, width_index: int) -> None:
    """TS-IND-098: a pivot at p is absent from bars[:p+w] and present in bars[:p+w+1]."""
    width = (3, 5, 8)[width_index - 1]
    full = pivots(bundle.high, bundle.low, width)
    n = len(bundle)
    assert all(pv.index + width <= n - 1 for pv in full)  # never within w bars of the end
    for pv in full[:: max(1, len(full) // 6)]:
        before = pivots(bundle.high[: pv.index + width], bundle.low[: pv.index + width], width)
        after = pivots(
            bundle.high[: pv.index + width + 1], bundle.low[: pv.index + width + 1], width
        )
        assert (pv.index, pv.kind) not in {(p.index, p.kind) for p in before}
        assert (pv.index, pv.kind) in {(p.index, p.kind) for p in after}


@given(bundles(max_len=450), st.data())
def test_prop_weekly_values_use_only_bars_up_to_t(bundle: Bundle, data: st.DataObject) -> None:
    """TS-IND-099: weekly resampling and weekly divergences, TEST_PLAN 6.1 item 6.

    The value reported at day t uses only bars <= t (checked for the daily-aligned weekly
    indicators by TS-IND-090). Here: completed weeks never change when later days arrive, and a
    weekly divergence as of a completed week equals the one computed with the data cut at that
    week's last session. A partial last week may be revised once the week completes; that is not
    look-ahead (the earlier report used only the bars then available).
    """
    n = len(bundle)
    t = data.draw(st.integers(FIXED_FIRST_CUT - 50, n - 2))
    h = bundle.head(t + 1)

    def weekly(b: Bundle) -> object:
        return resample_weekly(b.dates, b.open, b.high, b.low, b.close, b.volume)

    full_w, part_w = weekly(bundle), weekly(h)
    done = len(part_w.close) - 1  # weeks before t's (possibly partial) week
    for field in ("open", "high", "low", "close", "volume", "sessions"):
        assert np.array_equal(getattr(full_w, field)[:done], getattr(part_w, field)[:done])
    # partial week: only bars up to t
    last_week = np.flatnonzero(full_w.week_index[: t + 1] == full_w.week_index[t])
    assert part_w.close[-1] == bundle.close[t]
    assert part_w.volume[-1] == bundle.volume[last_week].sum()
    assert part_w.high[-1] == bundle.high[last_week].max()

    # weekly divergences as of a completed week
    ends = np.flatnonzero(np.diff(full_w.week_index.astype(np.int64)) != 0)
    ends = ends[ends >= 100]
    cut = int(ends[len(ends) // 2])
    w = int(full_w.week_index[cut])
    a = detect_weekly_divergences(weekly(bundle), as_of=w)
    b = detect_weekly_divergences(weekly(bundle.head(cut + 1)))
    assert a == b
