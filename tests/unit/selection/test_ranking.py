# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Ranking, tie-breakers, pick counts, nearest miss and `select` (TS-SEL; S3-T06; FR-404 to
FR-412).

Seed config: 3 buys, 2 sells, buy display >= 65, sell display <= 35. Expected orders are read off
the spec by hand, never from the code under test.
"""

from __future__ import annotations

import ast
import dataclasses
import re
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from supertrends import selection
from supertrends.selection.candidates import (
    REASON_RC_SELL,
    Exclusion,
    SelectionInput,
)
from supertrends.selection.ranking import (
    NearestMiss,
    PriorPicks,
    Selection,
    days_on_list,
    nearest_miss,
    rank_candidates,
    rank_key,
    select,
)
from tests.unit.selection.sel_support import (
    buy,
    cfg,
    independent_closes,
    near_duplicate_closes,
    sell,
    with_selection,
)


def _tickers(entries: Any) -> list[str]:
    return [e.ticker for e in entries]


def _run(entries: list[SelectionInput], **kwargs: Any) -> Selection:
    closes = independent_closes(sorted({e.ticker for e in entries}))
    return select(entries, closes, kwargs.pop("config", cfg()), **kwargs)


# --- ranking and tie-breakers (TS-SEL-016 to TS-SEL-022) -------------------------------------


def test_unit_selection_rank_buys_by_display_descending() -> None:
    """TS-SEL-016: FR-404 example, buys with display 72, 81, 68 rank 81, 72, 68."""
    entries = [buy("A", 72.0), buy("B", 81.0), buy("C", 68.0)]
    assert _tickers(rank_candidates(entries, "buy")) == ["B", "A", "C"]
    assert [p.ticker for p in _run(entries).buys] == ["B", "A", "C"]
    assert [p.rank for p in _run(entries).buys] == [1, 2, 3]


def test_unit_selection_rank_sells_by_display_ascending() -> None:
    """TS-SEL-017: sells with display 30, 12, 25 rank 12, 25, 30; two are published."""
    entries = [sell("A", 30.0), sell("B", 12.0), sell("C", 25.0)]
    assert _tickers(rank_candidates(entries, "sell")) == ["B", "C", "A"]
    assert [p.ticker for p in _run(entries).sells] == ["B", "C"]


def test_unit_selection_tiebreak_equal_display_higher_confidence_wins() -> None:
    """TS-SEL-018: equal display 70; confidence 65 beats 60 even with an older flip."""
    entries = [
        buy("A", confidence=60.0, bars_since_flip=1),
        buy("B", confidence=65.0, bars_since_flip=9),
    ]
    assert _tickers(rank_candidates(entries, "buy")) == ["B", "A"]
    sells = [sell("A", confidence=60.0), sell("B", confidence=65.0)]
    assert _tickers(rank_candidates(sells, "sell")) == ["B", "A"]


def test_unit_selection_tiebreak_equal_confidence_more_recent_flip_wins() -> None:
    """TS-SEL-019: FR-405 example, bars_since_flip 2 beats 7, even with lower relative volume."""
    entries = [
        buy("A", bars_since_flip=7, relative_volume=3.0),
        buy("B", bars_since_flip=2, relative_volume=0.5),
    ]
    assert _tickers(rank_candidates(entries, "buy")) == ["B", "A"]


def test_unit_selection_tiebreak_equal_flip_higher_relative_volume_wins() -> None:
    """TS-SEL-020: equal display, confidence and flip age; relative volume 1.8 beats 1.2 even
    when its ticker sorts later."""
    entries = [buy("AAA", relative_volume=1.2), buy("ZZZ", relative_volume=1.8)]
    assert _tickers(rank_candidates(entries, "buy")) == ["ZZZ", "AAA"]


def test_unit_selection_tiebreak_all_equal_alphabetical_ticker_wins() -> None:
    """TS-SEL-021: all else equal, AAPL ranks before MSFT on both sides."""
    assert _tickers(rank_candidates([buy("MSFT"), buy("AAPL")], "buy")) == ["AAPL", "MSFT"]
    assert _tickers(rank_candidates([sell("MSFT"), sell("AAPL")], "sell")) == ["AAPL", "MSFT"]


TIE_SET = [
    buy("D", 70.0, confidence=60.0, bars_since_flip=3, relative_volume=1.0),
    buy("C", 70.0, confidence=60.0, bars_since_flip=3, relative_volume=1.0),
    buy("B", 70.0, confidence=60.0, bars_since_flip=2, relative_volume=1.0),
    buy("A", 70.0, confidence=55.0, bars_since_flip=1, relative_volume=4.0),
    buy("E", 70.0, confidence=60.0, bars_since_flip=3, relative_volume=2.0),
    buy("F", 90.0, confidence=50.0),
    sell("S1", 20.0),
    sell("S2", 20.0, confidence=70.0),
    sell("S3", 10.0),
]
# By hand: F (90); then the 70s by confidence 60 > 55; among the 60s flip 2 (B) first; then
# flip 3 by relative volume 2.0 (E); then C, D alphabetical; A last. Top 3 buys: F, B, E.
# Sells: S3 (10), then S2 (20, conf 70) before S1 (20, conf 60).
TIE_CLOSES = independent_closes([e.ticker for e in TIE_SET])


@given(st.permutations(TIE_SET))
def test_prop_selection_rank_independent_of_input_order(entries: list[SelectionInput]) -> None:
    """TS-SEL-022: any input order gives the same ranking and the same picks."""
    buys = [e for e in entries if e.st_dir_d == 1]
    assert _tickers(rank_candidates(buys, "buy")) == ["F", "B", "E", "C", "D", "A"]
    result = select(entries, TIE_CLOSES, cfg())
    assert [p.ticker for p in result.buys] == ["F", "B", "E"]
    assert [p.ticker for p in result.sells] == ["S3", "S2"]
    assert result == select(TIE_SET, TIE_CLOSES, cfg())


# --- counts and never pad (TS-SEL-023 to TS-SEL-027) -----------------------------------------


def test_unit_selection_publish_top_3_buys_and_top_2_sells_by_default() -> None:
    """TS-SEL-023: FR-406 example, 8 qualifying buys and 5 sells -> exactly 3 and 2."""
    buys = [buy(f"B{i}", 66.0 + i) for i in range(8)]
    sells = [sell(f"S{i}", 34.0 - i) for i in range(5)]
    result = _run(buys + sells)
    assert [p.ticker for p in result.buys] == ["B7", "B6", "B5"]
    assert [p.ticker for p in result.sells] == ["S4", "S3"]
    assert result.nearest_miss == {"buy": None, "sell": None}


def test_unit_selection_max_counts_read_from_config_selection_keys() -> None:
    """TS-SEL-024: `selection.max_buys` 1 and `max_sells` 4 give 1 buy and 4 sells."""
    assert (cfg().selection.max_buys, cfg().selection.max_sells) == (3, 2)
    custom = with_selection(cfg(), max_buys=1, max_sells=4)
    buys = [buy(f"B{i}", 66.0 + i) for i in range(5)]
    sells = [sell(f"S{i}", 34.0 - i) for i in range(5)]
    result = _run(buys + sells, config=custom)
    assert [p.ticker for p in result.buys] == ["B4"]
    assert [p.ticker for p in result.sells] == ["S4", "S3", "S2", "S1"]


def test_unit_selection_only_one_qualifying_buy_result_has_one_buy_not_three() -> None:
    """TS-SEL-025: FR-407, exactly 1 qualifying buy -> 1 buy; non-qualifiers never pad."""
    entries = [
        buy("ONLY", 70.0),
        buy("LOW", 64.9),
        buy("DOWN", 80.0, st_dir_d=-1),
        buy("WEAK", 75.0, confidence=40.0),
    ]
    result = _run(entries)
    assert [p.ticker for p in result.buys] == ["ONLY"]
    assert len(result.buys) == 1


def test_unit_selection_zero_qualifying_sells_result_has_empty_sell_side() -> None:
    """TS-SEL-026: no sell qualifies -> the sell side is empty, which is a valid result."""
    result = _run([buy("A"), buy("B", 50.0)])
    assert result.sells == ()


def test_unit_selection_empty_side_records_nearest_miss_with_reason() -> None:
    """TS-SEL-027: FR-408, no sells; XYZ at 37.2 is nearest to 35 (2.2 away) -> nearest miss."""
    entries = [
        buy("A", 70.0),
        sell("XYZ", 37.2),
        sell("FAR", 45.0),
    ]
    result = _run(entries)
    assert result.sells == ()
    assert result.nearest_miss["sell"] == NearestMiss(
        ticker="XYZ",
        side="sell",
        display_score=37.2,
        threshold=35.0,
        reason="score above the sell threshold of 35",
    )
    # 1 of 3 buys: the buy side also records its nearest miss (FAR 45 is 20 below 65,
    # XYZ 37.2 is 27.8 below).
    miss = result.nearest_miss["buy"]
    assert miss is not None
    assert (miss.ticker, miss.reason) == ("FAR", "score below the buy threshold of 65")


# --- exclusions, stickiness, day count, wording (TS-SEL-035 to TS-SEL-038, TS-SEL-045) -------


def test_unit_selection_excluded_stale_and_insufficient_history_listed_with_reasons() -> None:
    """TS-SEL-035: FR-412, excluded tickers are listed with reasons and are never candidates or
    nearest misses, even if a score for them is passed in."""
    excluded = [Exclusion("NEW", "insufficient_history"), Exclusion("ABC", "stale")]
    entries = [buy("A", 70.0), buy("ABC", 90.0), sell("NEW", 36.0), sell("FAR", 50.0)]
    result = _run(entries, excluded=excluded)
    assert result.excluded == (Exclusion("ABC", "stale"), Exclusion("NEW", "insufficient_history"))
    assert [p.ticker for p in result.buys] == ["A"]
    assert {c.ticker for c in result.checks} == {"A", "FAR"}
    sell_miss = result.nearest_miss["sell"]
    assert sell_miss is not None
    assert sell_miss.ticker != "NEW"


def test_unit_selection_stickiness_none_ticker_may_repeat_consecutive_days() -> None:
    """TS-SEL-036: no stickiness: yesterday's picks neither help nor block today's."""
    entries = [buy("ORCL", 70.0), buy("NVDA", 72.0), sell("XOM", 30.0)]
    plain = _run(entries)
    prior = [PriorPicks(buys=frozenset({"ORCL", "AMD"}), sells=frozenset({"XOM"}))]
    sticky = _run(entries, previous=prior)
    assert [p.ticker for p in sticky.buys] == [p.ticker for p in plain.buys] == ["NVDA", "ORCL"]
    assert [p.ticker for p in sticky.sells] == ["XOM"]
    assert "AMD" not in [p.ticker for p in sticky.buys]


def test_unit_selection_day_n_on_list_counter_counts_consecutive_days() -> None:
    """TS-SEL-037: FR-411, ORCL a buy on the previous two published days and today -> 3."""
    orcl = PriorPicks(frozenset({"ORCL"}), frozenset())
    two = [orcl, orcl]
    assert days_on_list("ORCL", "buy", two) == 3
    assert days_on_list("ORCL", "buy", []) == 1
    gap = [PriorPicks(frozenset(), frozenset()), PriorPicks(frozenset({"ORCL"}), frozenset())]
    assert days_on_list("ORCL", "buy", gap) == 1
    other_side = [PriorPicks(frozenset(), frozenset({"ORCL"}))]
    assert days_on_list("ORCL", "buy", other_side) == 1
    assert days_on_list("ORCL", "sell", other_side) == 2
    result = _run([buy("ORCL")], previous=two)
    assert result.buys[0].days_on_list == 3


SHORTING_WORDS = re.compile(
    r"\b(short|shorting|put|puts|call|calls|option|options|expiry|expiration|contract|"
    r"leverage|margin|shares|position size)\b",
    re.IGNORECASE,
)


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return [s for f in dataclasses.fields(value) for s in _strings(getattr(value, f.name))]
    if isinstance(value, dict | tuple | list) or hasattr(value, "items"):
        items = value.items() if hasattr(value, "items") else enumerate(value)
        return [s for k, v in items for s in _strings(k) + _strings(v)]
    return []


def test_unit_selection_sell_is_bearish_label_no_short_instruction_in_output() -> None:
    """TS-SEL-038: FR-403, a sell is labelled "sell" and no text in the selection result carries
    a short-selling, instrument, size or expiry instruction."""
    entries = [sell("XOM", 30.0), sell("CVX", 34.0, rc_bias=1), buy("A", 66.0, confidence=40.0)]
    result = _run(entries)
    assert [p.side for p in result.sells] == ["sell"]
    texts = [s for s in _strings(dataclasses.replace(result, buys=(), sells=())) if " " in s]
    texts += [r for c in result.checks for r in c.buy.reasons + c.sell.reasons]
    assert texts  # reasons exist
    assert [t for t in texts if SHORTING_WORDS.search(t)] == []


def test_unit_selection_ripster_gate_rejection_listed_in_nearest_miss_reasons() -> None:
    """TS-SEL-045: the only sell-scored ticker closes above the 34/50 cloud; with no sells the
    nearest miss names it with the gate reason."""
    result = _run([buy("A"), sell("CVX", 30.0, rc_bias=1)])
    assert result.sells == ()
    assert result.nearest_miss["sell"] == NearestMiss("CVX", "sell", 30.0, 35.0, REASON_RC_SELL)


# --- added scenarios (TS-SEL-105, TS-SEL-106, TS-SEL-111 to TS-SEL-115) ----------------------


def test_unit_selection_nearest_miss_score_clearing_threshold_is_distance_zero() -> None:
    """TS-SEL-105: distance is the score shortfall (0 when the score clears the bar). A (64.5)
    is 0.5 short; B (72, confidence 45) and C (75, direction down) are 0 short; the tie goes to
    the buy ranking (display 75 first), so C is the nearest miss."""
    entries = [buy("A", 64.5), buy("B", 72.0, confidence=45.0), buy("C", 75.0, st_dir_d=-1)]
    assert nearest_miss(entries, "buy", cfg()) == NearestMiss(
        "C", "buy", 75.0, 65.0, "Supertrend direction is down"
    )
    sells = [sell("X", 35.5), sell("Y", 20.0, confidence=45.0), sell("Z", 30.0, st_dir_d=1)]
    # Y and Z clear 35; the sell ranking puts display 20 first.
    assert nearest_miss(sells, "sell", cfg()) == NearestMiss(
        "Y", "sell", 20.0, 35.0, "confidence 45 below 50"
    )


def test_unit_selection_nearest_miss_uses_adjusted_threshold() -> None:
    """TS-SEL-105: with a +10 buy shift, A at 70 is 5 short of 75 and B at 62 is 3 short of 65,
    so B is nearer."""
    entries = [buy("A", 70.0, buy_shift=10.0), buy("B", 62.0)]
    miss = nearest_miss(entries, "buy", cfg())
    assert miss == NearestMiss("B", "buy", 62.0, 65.0, "score below the buy threshold of 65")


def test_unit_selection_nearest_miss_absent_when_full_or_nothing_missed() -> None:
    """TS-SEL-106: a full side has no nearest miss; stale and guard-skipped candidates are not
    misses; with only those left the nearest miss is None."""
    full = _run([buy("A", 70.0), buy("B", 71.0), buy("C", 72.0), buy("D", 60.0)])
    assert full.nearest_miss["buy"] is None
    only_stale = _run([sell("OLD", 30.0, quality="stale")])
    assert only_stale.nearest_miss == {"buy": None, "sell": None}
    dup_closes = near_duplicate_closes(7, ["SPY", "VOO"])
    dups = select([buy("SPY", 80.0), buy("VOO", 79.0)], dup_closes, cfg())
    assert [p.ticker for p in dups.buys] == ["SPY"]
    assert dups.nearest_miss["buy"] is None  # VOO qualified; it is not a miss
    assert nearest_miss([buy("Q", 70.0)], "buy", cfg()) is None


def test_unit_selection_select_rejects_duplicate_tickers_and_bad_side() -> None:
    """TS-SEL-111: the same ticker twice is a ValueError; so is an unknown side."""
    with pytest.raises(ValueError, match="duplicate"):
        _run([buy("A"), buy("A", 80.0)])
    with pytest.raises(ValueError, match="side"):
        rank_key(buy("A"), "hold")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="side"):
        days_on_list("A", "hold", [])  # type: ignore[arg-type]


def test_unit_selection_select_is_pure_and_deterministic() -> None:
    """TS-SEL-112: same inputs give an equal result; inputs are not mutated."""
    entries = [buy("A", 70.0), buy("B", 75.0), sell("C", 20.0), sell("D", 40.0)]
    closes = independent_closes(["A", "B", "C", "D"])
    before = (list(entries), {k: dict(v) for k, v in closes.items()})
    first = select(entries, closes, cfg())
    assert first == select(entries, closes, cfg())
    assert (entries, closes) == before
    assert [c.ticker for c in first.checks] == ["A", "B", "C", "D"]
    pick = first.buys[0]
    assert (pick.ticker, pick.display_score, pick.confidence, pick.band) == (
        "B",
        75.0,
        60.0,
        entries[1].card.band,
    )
    assert pick.entry is entries[1]


def test_unit_selection_import_boundary_no_api_cli_mcp_data_runs() -> None:
    """TS-SEL-113: selection imports nothing from api, cli, mcp, data, runs or narrative."""
    forbidden = ("api", "cli", "mcp", "data", "runs", "narrative")
    root = Path(selection.__file__).parent
    files = sorted(root.glob("*.py"))
    assert len(files) == 4
    offenders: list[str] = []
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                parts = name.split(".")
                if parts[0] == "supertrends" and len(parts) > 1 and parts[1] in forbidden:
                    offenders.append(f"{path.name}: {name}")
            impure = {"random", "time", "os", "socket", "datetime.datetime"}
            offenders += [f"{path.name}: {n}" for n in names if n.split(".")[0] in impure]
    assert offenders == []


def test_unit_selection_null_tie_breakers_rank_last() -> None:
    """TS-SEL-114: an unknown flip age ranks after any known one; an unknown relative volume
    ranks after any known one."""
    flips = [buy("A", bars_since_flip=None), buy("B", bars_since_flip=50)]
    assert _tickers(rank_candidates(flips, "buy")) == ["B", "A"]
    vols = [buy("A", relative_volume=None), buy("B", relative_volume=0.1)]
    assert _tickers(rank_candidates(vols, "sell")) == ["B", "A"]


def test_unit_selection_max_zero_publishes_nothing_and_no_nearest_miss() -> None:
    """TS-SEL-115: `max_buys: 0` publishes no buys; the side is full, so no nearest miss."""
    result = _run([buy("A"), buy("B", 50.0)], config=with_selection(cfg(), max_buys=0))
    assert result.buys == ()
    assert result.nearest_miss["buy"] is None
