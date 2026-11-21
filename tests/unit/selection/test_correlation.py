# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Correlation guard and "also qualified" (TS-SEL; S3-T06; FR-409, FR-410).

Hand values: returns of [100, 110, 99] are [+0.10, -0.10]; Pearson of [1, 2, 3] with [2, 4, 6] is
+1 and with [3, 2, 1] is -1. Near-duplicate stand-ins share one return series plus noise 20 times
smaller, so their correlation is about 0.999; independent seeded series are far below 0.9.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from supertrends.selection.correlation import (
    CorrelationFn,
    Duplicate,
    correlation_guard,
    pearson,
    return_correlation,
    simple_returns,
)
from supertrends.selection.ranking import select
from tests.unit.selection.sel_support import (
    START,
    buy,
    cfg,
    closes_from_returns,
    independent_closes,
    near_duplicate_closes,
    random_returns,
    sell,
    with_selection,
)


def _table(values: dict[tuple[str, str], float]) -> CorrelationFn:
    def corr(a: str, b: str) -> float | None:
        return values.get((a, b), values.get((b, a)))

    return corr


def test_unit_selection_correlation_guard_skips_candidate_above_0_9_with_selected_pick() -> None:
    """TS-SEL-028: B correlates 0.95 with the picked A, so B is skipped and C is picked."""
    corr = _table({("A", "B"): 0.95, ("A", "C"): 0.1, ("B", "C"): 0.1})
    result = correlation_guard(["A", "B", "C"], corr, max_picks=3, max_correlation=0.9)
    assert result.picked == ("A", "C")
    assert result.skipped == (Duplicate("B", "A", 0.95),)


@pytest.mark.parametrize(
    ("value", "skipped"),
    [
        pytest.param(0.9, False, id="exactly-0.9"),
        pytest.param(math.nextafter(0.9, 1.0), True, id="just-above"),
    ],
)
def test_unit_selection_correlation_guard_exactly_0_9_is_not_skipped(
    value: float, skipped: bool
) -> None:
    """TS-SEL-029: the rule is "above 0.9": 0.9 itself is kept, the next double up is skipped."""
    corr = _table({("A", "B"): value})
    result = correlation_guard(["A", "B"], corr, max_picks=2, max_correlation=0.9)
    assert result.picked == (("A",) if skipped else ("A", "B"))


def test_unit_selection_correlation_guard_spy_voo_ivv_only_top_one_selected() -> None:
    """TS-SEL-030: SPY, VOO, IVV stand-ins all qualify; only the top one (SPY) is picked and the
    side fills with the next non-duplicates (ORCL, NVDA)."""
    entries = [
        buy("SPY", 80.0),
        buy("VOO", 79.0),
        buy("IVV", 78.0),
        buy("ORCL", 75.0),
        buy("NVDA", 72.0),
    ]
    closes = near_duplicate_closes(7, ["SPY", "VOO", "IVV"]) | independent_closes(["ORCL", "NVDA"])
    for a, b in (("SPY", "VOO"), ("SPY", "IVV"), ("VOO", "IVV")):
        corr = return_correlation(closes[a], closes[b], 60)
        assert corr is not None
        assert corr > 0.99
    result = select(entries, closes, cfg())
    picked = [p.ticker for p in result.buys]
    assert picked == ["SPY", "ORCL", "NVDA"]
    assert len({"SPY", "VOO", "IVV"} & set(picked)) == 1


def test_unit_selection_correlation_guard_skipped_listed_as_also_qualified_with_duplicate_of() -> (
    None
):
    """TS-SEL-031: VOO and IVV, skipped because of SPY, are "also qualified" with duplicates SPY."""
    entries = [buy("SPY", 80.0), buy("VOO", 79.0, confidence=70.0), buy("IVV", 78.0)]
    closes = near_duplicate_closes(7, ["SPY", "VOO", "IVV"])
    result = select(entries, closes, cfg())
    assert [p.ticker for p in result.buys] == ["SPY"]
    also = result.also_qualified
    assert [(a.ticker, a.side, a.duplicates) for a in also] == [
        ("VOO", "buy", "SPY"),
        ("IVV", "buy", "SPY"),
    ]
    assert also[0].display_score == 79.0
    assert also[0].confidence == 70.0
    assert also[0].correlation > 0.9
    assert also[0].entry is entries[1]


def test_unit_selection_correlation_guard_applied_per_side_not_across_sides() -> None:
    """TS-SEL-032: a sell perfectly correlated with a buy pick is still picked as a sell."""
    base = random_returns(3)
    closes = {
        "BUYA": closes_from_returns(base),
        "SELLB": closes_from_returns(base, start=50.0),  # identical returns -> correlation 1
    }
    result = select([buy("BUYA"), sell("SELLB")], closes, cfg())
    assert [p.ticker for p in result.buys] == ["BUYA"]
    assert [p.ticker for p in result.sells] == ["SELLB"]
    assert result.also_qualified == ()


def test_unit_selection_correlation_guard_uses_60_day_return_window() -> None:
    """TS-SEL-033: the last 60 returns of B equal A's, the 60 before are A's negated. Over 60 the
    correlation is 1 (B skipped); with a 120-day window it is about 0 (B kept)."""
    a = random_returns(11, n=120)
    b = [-r for r in a[:60]] + a[60:]
    closes = {"A": closes_from_returns(a), "B": closes_from_returns(b)}
    assert cfg().selection.correlation_window == 60
    corr60 = return_correlation(closes["A"], closes["B"], 60)
    assert corr60 is not None
    assert corr60 == pytest.approx(1.0, abs=1e-9)
    entries = [buy("A", 80.0), buy("B", 79.0)]
    assert [p.ticker for p in select(entries, closes, cfg()).buys] == ["A"]
    wide = with_selection(cfg(), correlation_window=120)
    assert [p.ticker for p in select(entries, closes, wide).buys] == ["A", "B"]


def test_unit_selection_correlation_guard_walks_past_skipped_to_fill_side() -> None:
    """TS-SEL-034: picks A; B and C duplicate A; D duplicates nothing and fills the second slot."""
    corr = _table({("A", "B"): 0.95, ("A", "C"): 0.97, ("A", "D"): 0.2, ("A", "E"): 0.1})
    result = correlation_guard(["A", "B", "C", "D", "E"], corr, max_picks=2, max_correlation=0.9)
    assert result.picked == ("A", "D")
    assert [d.ticker for d in result.skipped] == ["B", "C"]


# --- added scenarios (TS-SEL-107 to TS-SEL-110) ----------------------------------------------


def test_unit_selection_simple_returns_and_pearson_hand_values() -> None:
    """TS-SEL-108: returns of 100, 110, 99 are +0.10, -0.10; Pearson +1 and -1 on lines."""
    assert simple_returns([100.0, 110.0, 99.0]) == pytest.approx([0.10, -0.10])
    assert simple_returns([100.0]) == []
    assert pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == pytest.approx(1.0)
    assert pearson([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) == pytest.approx(-1.0)
    # x = [1, 2, 3, 4], y = [1, 3, 2, 4]: sxy = 4, sxx = syy = 5 -> 0.8
    assert pearson([1.0, 2.0, 3.0, 4.0], [1.0, 3.0, 2.0, 4.0]) == pytest.approx(0.8)


def test_unit_selection_pearson_undefined_cases() -> None:
    """TS-SEL-107: fewer than 2 points or a flat series has no correlation (None)."""
    assert pearson([1.0], [2.0]) is None
    assert pearson([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None
    with pytest.raises(ValueError, match="length"):
        pearson([1.0, 2.0], [1.0])


def test_unit_selection_return_correlation_uses_shared_dates_only() -> None:
    """TS-SEL-108: dates only one series has are ignored; returns span the shared dates."""
    days = [START + timedelta(days=i) for i in range(4)]
    a = {days[0]: 100.0, days[1]: 101.0, days[2]: 103.0, days[3]: 102.0}
    # b lacks days[1]; shared dates 0, 2, 3 -> two returns each (+,-) for both, so Pearson is +1
    b = {days[0]: 50.0, days[2]: 53.0, days[3]: 52.0, date(2027, 1, 1): 10.0}
    assert return_correlation(a, b, 2) == pytest.approx(1.0)


def test_unit_selection_correlation_undefined_never_skips() -> None:
    """TS-SEL-107: too little shared history, a flat series, or no closes is not "above 0.9"."""
    short = closes_from_returns(random_returns(5, n=30))
    assert return_correlation(short, short, 60) is None
    flat = closes_from_returns([0.0] * 80)
    other = closes_from_returns(random_returns(6))
    assert return_correlation(flat, other, 60) is None
    entries = [buy("A", 80.0), buy("B", 79.0), buy("C", 78.0)]
    closes = {"A": short, "B": short}  # C has no closes at all
    assert [p.ticker for p in select(entries, closes, cfg()).buys] == ["A", "B", "C"]


def test_unit_selection_return_correlation_rejects_bad_input() -> None:
    """TS-SEL-111: a non-positive or non-finite close and a window below 2 are ValueErrors."""
    good = closes_from_returns(random_returns(8))
    last = max(good)  # only the last window + 1 shared dates are read
    bad = dict(good)
    bad[last] = 0.0
    with pytest.raises(ValueError, match="close"):
        return_correlation(bad, good, 60)
    nan = dict(good)
    nan[last] = math.nan
    with pytest.raises(ValueError, match="close"):
        return_correlation(good, nan, 60)
    with pytest.raises(ValueError, match="window"):
        return_correlation(good, good, 1)


def test_unit_selection_duplicate_names_most_correlated_pick() -> None:
    """TS-SEL-109: C duplicates both picks A (0.92) and B (0.97); it is listed under B."""
    corr = _table({("A", "B"): 0.1, ("A", "C"): 0.92, ("B", "C"): 0.97})
    result = correlation_guard(["A", "B", "C"], corr, max_picks=3, max_correlation=0.9)
    assert result.skipped == (Duplicate("C", "B", 0.97),)
    tie = _table({("A", "B"): 0.1, ("A", "C"): 0.95, ("B", "C"): 0.95})
    tied = correlation_guard(["A", "B", "C"], tie, max_picks=3, max_correlation=0.9)
    assert tied.skipped == (Duplicate("C", "A", 0.95),)  # equal: the higher-ranked pick


def test_unit_selection_candidates_after_side_full_not_walked() -> None:
    """TS-SEL-110: the walk stops when the side is full, so a later duplicate is not listed."""
    corr = _table({("A", "B"): 0.1, ("A", "C"): 0.99})
    result = correlation_guard(["A", "B", "C"], corr, max_picks=2, max_correlation=0.9)
    assert result.picked == ("A", "B")
    assert result.skipped == ()
    empty = correlation_guard(["A"], corr, max_picks=0, max_correlation=0.9)
    assert empty.picked == ()
