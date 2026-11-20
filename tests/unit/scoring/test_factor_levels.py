# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 7, Support and resistance (S3-T03; BUILD_PROMPT Factor 7; PRD FR-310; 10.4.7).

`rr = d_r / max(d_s, 0.25)`, `base = clip((rr - 1) * 40, -60, 60)`, +40 breakout, -40 breakdown
(relative volume >= 1.5, the level intact yesterday), `score = clip(base + breakout, -100, 100)`.
The support and resistance block is the indicator output as the snapshot carries it.
"""

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from supertrends.scoring.config import ScoringConfig, load_scoring_config
from supertrends.scoring.factor import FactorContext, Quality
from supertrends.scoring.factors.levels import FACTOR
from supertrends.scoring.snapshot import compute_snapshot
from tests.unit.indicators.lookahead_support import make_bundle

CONFIG = Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"


@pytest.fixture(scope="module")
def cfg() -> ScoringConfig:
    return load_scoring_config(CONFIG)


@pytest.fixture(scope="module")
def ctx(cfg: ScoringConfig) -> FactorContext:
    return FactorContext(config=cfg, as_of=date(2026, 1, 2))


def snap(
    d_s: float | None,
    d_r: float | None,
    *,
    rv: float | None = 1.0,
    breakout: bool = False,
    breakdown: bool = False,
    close: float = 100.0,
    atr: float = 2.0,
    high52: float = 130.0,
    low52: float = 70.0,
) -> dict[str, Any]:
    sup = None if d_s is None else {"price": close - d_s * atr, "strength": 1.0, "touches": 2}
    res = None if d_r is None else {"price": close + d_r * atr, "strength": 1.0, "touches": 2}
    broken = None
    if breakout:
        broken = close - 0.5
    if breakdown:
        broken = close + 0.5
    return {
        "daily": {"close": close, "atr": atr, "relative_volume": rv},
        "levels": {
            "high_52w": high52,
            "low_52w": low52,
            "support_resistance": {
                "d_s": d_s,
                "d_r": d_r,
                "nearest_support": sup,
                "nearest_resistance": res,
                "rel_volume": rv,
                "breakout": breakout,
                "breakdown": breakdown,
                "broken_level": broken,
            },
        },
    }


@pytest.mark.parametrize(
    ("d_s", "d_r", "expected"),
    [
        (1.0, 1.5, 20.0),  # rr 1.5 -> (1.5-1)*40 = 20
        (1.0, 0.5, -20.0),  # rr 0.5 -> -20
        (1.0, 2.0, 40.0),  # rr 2 -> 40
        (1.0, 2.5, 60.0),  # rr 2.5 -> 60, exactly the cap
        (1.0, 3.0, 60.0),  # rr 3 -> 80, clipped to 60
        (0.5, 0.0, -40.0),  # no room above: rr 0 -> -40 (the lowest base reachable)
        (2.0, 1.0, -20.0),  # rr 0.5
        (4.0, 8.0, 40.0),  # rr 2
    ],
)
def test_unit_levels_score_rr_formula_room_above_vs_below_base_clip_60(
    ctx: FactorContext, d_s: float, d_r: float, expected: float
) -> None:
    """TS-SCR-120: `rr = d_r / max(d_s, 0.25)`, `base = clip((rr-1)*40, -60, 60)`."""
    assert FACTOR.compute(snap(d_s, d_r), ctx).score == pytest.approx(expected)


@pytest.mark.parametrize(
    ("d_s", "d_r", "expected"),
    [
        (0.0, 0.5, 40.0),  # floor 0.25 -> rr 2 -> 40
        (0.1, 0.5, 40.0),  # 0.1 < 0.25 -> floor -> rr 2
        (0.2499, 0.5, 40.0),  # still floored
        (0.5, 0.5, 0.0),  # above the floor: rr 1 -> 0
        (0.25, 0.75, 60.0),  # at the floor: rr 0.75/0.25 = 3 -> (3-1)*40 = 80 -> clipped to 60
    ],
)
def test_unit_levels_score_d_s_zero_uses_floor_0_25(
    ctx: FactorContext, d_s: float, d_r: float, expected: float
) -> None:
    """TS-SCR-121: the support distance is floored at 0.25 before dividing."""
    assert FACTOR.compute(snap(d_s, d_r), ctx).score == pytest.approx(expected)


@pytest.mark.parametrize(("d_s", "d_r"), [(1.0, 1.0), (0.25, 0.25), (0.1, 0.25), (3.0, 3.0)])
def test_unit_levels_score_rr_1_0_base_zero(ctx: FactorContext, d_s: float, d_r: float) -> None:
    """TS-SCR-122: rr exactly 1 (after the floor) -> base 0."""
    assert FACTOR.compute(snap(d_s, d_r), ctx).score == 0.0


@pytest.mark.parametrize(
    ("rv", "expected"),
    [
        (1.5, 60.0),  # base (d_s 1, d_r 1.5) = 20, +40 at the boundary -> 60
        (1.5001, 60.0),
        (3.0, 60.0),
    ],
)
def test_unit_levels_score_breakout_rel_volume_1_5_adds_40(
    ctx: FactorContext, rv: float, expected: float
) -> None:
    """TS-SCR-123: relative volume exactly 1.5 (inclusive) confirms the breakout: +40."""
    assert FACTOR.compute(snap(1.0, 1.5, rv=rv, breakout=True), ctx).score == expected


@pytest.mark.parametrize("rv", [1.49, 1.4999, 1.0, 0.0, None])
def test_unit_levels_score_breakout_rel_volume_1_49_adds_0(
    ctx: FactorContext, rv: float | None
) -> None:
    """TS-SCR-124: relative volume below 1.5 (or unknown) adds nothing; base only (20)."""
    assert FACTOR.compute(snap(1.0, 1.5, rv=rv, breakout=True), ctx).score == 20.0


def test_unit_levels_score_breakout_level_not_intact_yesterday_adds_0(ctx: FactorContext) -> None:
    """TS-SCR-125: no breakout flag (the level was not intact yesterday) adds 0, any volume."""
    # The indicator raises `breakout` only for a level that was a resistance at yesterday's
    # close; a close above a level that was already broken carries breakout False.
    res = FACTOR.compute(snap(1.0, 1.5, rv=3.0, breakout=False), ctx)
    assert res.score == 20.0  # base only
    assert "breakout" not in {e.name for e in res.evidence}


@pytest.mark.parametrize(
    ("d_s", "d_r", "rv", "expected"),
    [
        (1.0, 1.0, 1.5, -40.0),  # base 0, breakdown -> -40
        (1.0, 1.0, 1.49, 0.0),  # below the volume bar: nothing
        (1.0, 0.5, 2.0, -60.0),  # base -20, -40 -> -60
        (1.0, 0.0, 1.5, -80.0),  # base -40, -40 -> -80
    ],
)
def test_unit_levels_score_breakdown_rel_volume_1_5_subtracts_40(
    ctx: FactorContext, d_s: float, d_r: float, rv: float, expected: float
) -> None:
    """TS-SCR-126: close below an intact support on relative volume >= 1.5 -> -40."""
    assert FACTOR.compute(snap(d_s, d_r, rv=rv, breakdown=True), ctx).score == expected


@pytest.mark.parametrize(
    ("d_s", "d_r", "expected"),
    [
        (1.0, 3.0, 100.0),  # base 60 (rr 3 -> 80 capped) + 40 = 100
        (0.0, 5.0, 100.0),  # floor: rr 20 -> capped 60, + 40
    ],
)
def test_unit_levels_score_total_clipped_to_100(
    ctx: FactorContext, d_s: float, d_r: float, expected: float
) -> None:
    """TS-SCR-127: base 60 plus breakout 40 reaches, and never passes, 100."""
    assert FACTOR.compute(snap(d_s, d_r, rv=2.0, breakout=True), ctx).score == expected


def test_unit_levels_score_no_resistance_above_uses_52_week_high_level(
    ctx: FactorContext,
) -> None:
    """TS-SCR-128: with no resistance, the 52-week high (a level) gives the distance."""
    # close 100, atr 2, high_52w 110 -> d_r = (110-100)/2 = 5; d_s = 1 -> rr 5 -> 160 -> 60
    assert FACTOR.compute(snap(1.0, None, high52=110.0), ctx).score == 60.0
    # high_52w 102 -> d_r = 1; d_s 1 -> rr 1 -> 0
    assert FACTOR.compute(snap(1.0, None, high52=102.0), ctx).score == 0.0
    # high_52w 103 -> d_r 1.5, d_s 1 -> rr 1.5 -> 20
    assert FACTOR.compute(snap(1.0, None, high52=103.0), ctx).score == 20.0


def test_unit_levels_close_beyond_the_52_week_extreme_floors_distance_at_zero(
    ctx: FactorContext,
) -> None:
    """TS-SCR-370: close at or past the 52-week high leaves d_r 0 (not negative): rr 0 -> -40."""
    assert FACTOR.compute(snap(1.0, None, close=100.0, high52=100.0), ctx).score == -40.0
    assert FACTOR.compute(snap(1.0, None, close=105.0, high52=100.0), ctx).score == -40.0
    # mirror: no support, close at or below the 52-week low -> d_s 0 -> floor 0.25
    # d_r 0.5 -> rr 2 -> +40
    assert FACTOR.compute(snap(None, 0.5, close=100.0, low52=100.0), ctx).score == 40.0
    assert FACTOR.compute(snap(None, 0.5, close=95.0, low52=100.0), ctx).score == 40.0


def test_unit_levels_no_support_below_uses_52_week_low_level(ctx: FactorContext) -> None:
    """TS-SCR-371: with no support, the 52-week low gives d_s = (close-low)/atr."""
    # close 100, atr 2, low 90 -> d_s 5; d_r 2.5 -> rr 0.5 -> -20
    assert FACTOR.compute(snap(None, 2.5, low52=90.0), ctx).score == pytest.approx(-20.0)
    # low 98 -> d_s 1; d_r 3 -> rr 3 -> 60 (clipped)
    assert FACTOR.compute(snap(None, 3.0, low52=98.0), ctx).score == 60.0


def test_unit_levels_missing_inputs_make_the_factor_missing(ctx: FactorContext) -> None:
    """TS-SCR-372: no levels block, close, ATR (or zero) or 52-week range -> missing."""
    doc = snap(1.0, 1.0)
    doc["levels"]["support_resistance"] = None
    cases = [doc]
    for path in (
        ("daily", "close"),
        ("daily", "atr"),
        ("levels", "high_52w"),
        ("levels", "low_52w"),
    ):
        d = snap(1.0, 1.0)
        d[path[0]][path[1]] = None
        cases.append(d)
    zero_atr = snap(1.0, 1.0)
    zero_atr["daily"]["atr"] = 0.0
    cases.append(zero_atr)
    for case in cases:
        res = FACTOR.compute(case, ctx)
        assert (res.score, res.quality) == (0.0, Quality.MISSING)


def test_unit_levels_evidence_and_reasons_use_templates(ctx: FactorContext) -> None:
    """TS-SCR-373: evidence names, units and rendered reasons."""
    res = FACTOR.compute(snap(1.0, 1.5, rv=1.6, breakout=True), ctx)
    by_name = {e.name: e for e in res.evidence}
    assert by_name["d_s"].reason == "Nearest support is 1.00 ATR below the close"
    assert by_name["d_r"].reason == "Nearest resistance is 1.50 ATR above the close"
    assert by_name["rr"].reason == "Room above versus below is 1.50 to 1"
    assert by_name["nearest_support"].value == 98.0
    assert by_name["nearest_resistance"].value == 103.0
    assert by_name["range_52w"].reason == "The 52-week range is 70.00 to 130.00"
    # broken level is close - 0.5 = 99.5 in this fixture
    assert by_name["breakout"].reason == (
        "Close broke above resistance at 99.50 on relative volume 1.60"
    )
    assert by_name["base"].reason == "Room above versus below contributes 20.00 points"
    down = FACTOR.compute(snap(1.0, 1.0, rv=1.5, breakdown=True), ctx)
    assert {e.name: e for e in down.evidence}["breakdown"].reason == (
        "Close broke below support at 100.50 on relative volume 1.50"
    )


def test_unit_levels_on_real_snapshots_matches_independent_rr(
    ctx: FactorContext, cfg: ScoringConfig
) -> None:
    """TS-SCR-374: computed snapshots: in range, and equal to the rr formula on the snapshot."""
    for seed in range(8):
        bundle = make_bundle(seed=seed, n=400, intraday_from=None)
        doc = compute_snapshot(bundle, cfg, date.fromisoformat(str(bundle.dates[-1])))
        res = FACTOR.compute(doc, ctx)
        assert -100.0 <= res.score <= 100.0
        assert res.quality is Quality.OK
        sr = doc["levels"]["support_resistance"]
        atr = doc["daily"]["atr"]
        close = doc["daily"]["close"]
        d_s = sr["d_s"] if sr["d_s"] is not None else max(close - doc["levels"]["low_52w"], 0) / atr
        d_r = (
            sr["d_r"] if sr["d_r"] is not None else max(doc["levels"]["high_52w"] - close, 0) / atr
        )
        base = max(-60.0, min(60.0, (d_r / max(d_s, 0.25) - 1) * 40))
        extra = 0.0
        if doc["daily"]["relative_volume"] >= 1.5:
            extra = 40.0 * sr["breakout"] - 40.0 * sr["breakdown"]
        assert res.score == pytest.approx(max(-100.0, min(100.0, base + extra)))
