# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
# ruff: noqa: PLR0917
"""Factor 8, Volatility (S3-T03; BUILD_PROMPT Factor 8; PRD FR-311; TEST_PLAN 10.4.8).

`squeeze = bbw_rank < 15` -> +30 * st_dir_d; `expansion = bbw_rank > 85 and bbw rising 3 bars`
and close moved in the st_dir_d direction over 3 bars -> +20 * st_dir_d; the sum is halved when
`atr_pct_rank > 90`.
"""

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from supertrends.scoring.config import ScoringConfig, load_scoring_config
from supertrends.scoring.factor import FactorContext, Quality
from supertrends.scoring.factors.volatility import FACTOR
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
    direction: int | None = 1,
    bbw_rank: float | None = 50.0,
    *,
    expansion: float | None = 0.0,
    atr_rank: float | None = 50.0,
    close: float = 100.0,
    lag: float = 100.0,
    atr: float | None = 2.34,
) -> dict[str, Any]:
    squeeze = None if bbw_rank is None else float(bbw_rank < 15)
    return {
        "daily": {
            "squeeze": squeeze,
            "expansion": expansion,
            "atr_pct_rank": atr_rank,
            "bbw_rank": bbw_rank,
            "supertrend": {"direction": direction},
            "close": close,
            "close_lag_3": lag,
            "atr": atr,
            "atr_pct": 0.0234,
            "hv20": 0.31,
            "bandwidth": 0.12,
        }
    }


def test_unit_volatility_score_squeeze_up_trend_adds_30(ctx: FactorContext) -> None:
    """TS-SCR-130: squeeze with st_dir_d +1 -> +30."""
    assert FACTOR.compute(snap(1, 10.0), ctx).score == 30.0


def test_unit_volatility_score_squeeze_down_trend_subtracts_30(ctx: FactorContext) -> None:
    """TS-SCR-131: squeeze with st_dir_d -1 -> -30 (the sign follows the direction)."""
    assert FACTOR.compute(snap(-1, 10.0), ctx).score == -30.0


@pytest.mark.parametrize(
    ("rank", "expected"),
    [
        (0.0, 30.0),  # deepest compression
        (14.99, 30.0),  # 14.99 < 15
        (15.0, 0.0),  # strict: exactly 15 is not a squeeze
        (15.01, 0.0),
    ],
)
def test_unit_volatility_score_squeeze_boundary_rank_15_is_not_squeeze(
    ctx: FactorContext, rank: float, expected: float
) -> None:
    """TS-SCR-132: `bbw_rank < 15` is strict."""
    assert FACTOR.compute(snap(1, rank), ctx).score == expected


@pytest.mark.parametrize(
    ("direction", "close", "lag", "expected"),
    [
        (1, 103.0, 100.0, 20.0),  # up trend, close up over 3 bars: +20
        (-1, 97.0, 100.0, -20.0),  # down trend, close down over 3 bars: -20
        (1, 100.01, 100.0, 20.0),  # smallest move counts
    ],
)
def test_unit_volatility_score_expansion_with_move_in_trend_direction_adds_20(
    ctx: FactorContext, direction: int, close: float, lag: float, expected: float
) -> None:
    """TS-SCR-133: expansion and a 3-bar move in the trend direction -> `+20 * st_dir_d`."""
    res = FACTOR.compute(snap(direction, 90.0, expansion=1.0, close=close, lag=lag), ctx)
    assert res.score == expected


@pytest.mark.parametrize(
    ("direction", "close", "lag"),
    [
        (1, 97.0, 100.0),  # up trend, price fell
        (-1, 103.0, 100.0),  # down trend, price rose
        (1, 100.0, 100.0),  # no move is not a move in the direction
        (-1, 100.0, 100.0),
    ],
)
def test_unit_volatility_score_expansion_move_against_trend_adds_0(
    ctx: FactorContext, direction: int, close: float, lag: float
) -> None:
    """TS-SCR-134: the 3-bar move opposes (or does not follow) the direction -> 0."""
    res = FACTOR.compute(snap(direction, 90.0, expansion=1.0, close=close, lag=lag), ctx)
    assert res.score == 0.0


@pytest.mark.parametrize(
    ("direction", "rank", "expansion", "close", "lag", "expected"),
    [
        (1, 10.0, 0.0, 100.0, 100.0, 15.0),  # squeeze 30 * 0.5
        (-1, 10.0, 0.0, 100.0, 100.0, -15.0),  # -30 * 0.5
        (1, 90.0, 1.0, 103.0, 100.0, 10.0),  # expansion 20 * 0.5
        (-1, 90.0, 1.0, 97.0, 100.0, -10.0),  # -20 * 0.5
    ],
)
def test_unit_volatility_score_atr_pct_rank_above_90_halves_score(
    ctx: FactorContext,
    direction: int,
    rank: float,
    expansion: float,
    close: float,
    lag: float,
    expected: float,
) -> None:
    """TS-SCR-135: `atr_pct_rank > 90` multiplies the sum by 0.5."""
    doc = snap(direction, rank, expansion=expansion, atr_rank=90.01, close=close, lag=lag)
    assert FACTOR.compute(doc, ctx).score == expected
    assert FACTOR.compute({**doc, "daily": {**doc["daily"], "atr_pct_rank": 100.0}}, ctx).score == (
        expected
    )


@pytest.mark.parametrize(("direction", "expected"), [(1, 30.0), (-1, -30.0)])
def test_unit_volatility_score_atr_pct_rank_exactly_90_no_halving(
    ctx: FactorContext, direction: int, expected: float
) -> None:
    """TS-SCR-136: exactly 90 is not above 90 -> no halving."""
    assert FACTOR.compute(snap(direction, 10.0, atr_rank=90.0), ctx).score == expected


@pytest.mark.parametrize(
    ("rank", "expansion"),
    [(50.0, 0.0), (15.0, 0.0), (85.0, 0.0), (90.0, 0.0), (30.0, 1.0)],
)
def test_unit_volatility_score_neither_squeeze_nor_expansion_returns_zero(
    ctx: FactorContext, rank: float, expansion: float
) -> None:
    """TS-SCR-137: no rule -> 0 (also a stale expansion flag at a low rank, and a high rank
    without the rising band width)."""
    res = FACTOR.compute(snap(1, rank, expansion=expansion, close=105.0), ctx)
    assert res.score == 0.0
    assert res.quality is Quality.OK


def test_unit_volatility_evidence_expected_1d_move_equals_atr14(ctx: FactorContext) -> None:
    """TS-SCR-138: `expected_1d_move` equals atr14 on every result, whatever the score."""
    for doc in (snap(1, 10.0), snap(-1, 50.0), snap(1, 90.0, expansion=1.0, close=103.0)):
        by_name = {e.name: e for e in FACTOR.compute(doc, ctx).evidence}
        move = by_name["expected_1d_move"]
        assert move.value == 2.34
        assert move.unit == "price"
        assert move.reason == "Expected one-day move is 2.34 (ATR 14)"


def test_unit_volatility_expansion_rank_85_is_not_expansion(ctx: FactorContext) -> None:
    """TS-SCR-380: `bbw_rank > 85` is strict even when the flag is set."""
    assert FACTOR.compute(snap(1, 85.0, expansion=1.0, close=103.0), ctx).score == 0.0
    assert FACTOR.compute(snap(1, 85.01, expansion=1.0, close=103.0), ctx).score == 20.0


def test_unit_volatility_expansion_needs_the_rising_flag(ctx: FactorContext) -> None:
    """TS-SCR-381: a high rank without the snapshot expansion flag (bbw not rising) scores 0."""
    assert FACTOR.compute(snap(1, 95.0, expansion=0.0, close=103.0), ctx).score == 0.0
    assert FACTOR.compute(snap(1, 95.0, expansion=None, close=103.0), ctx).score == 0.0


def test_unit_volatility_null_atr_rank_or_atr_degrades(ctx: FactorContext) -> None:
    """TS-SCR-382: a null ATR rank (no halving possible) or ATR degrades; the score stays."""
    a = FACTOR.compute(snap(1, 10.0, atr_rank=None), ctx)
    assert (a.score, a.quality) == (30.0, Quality.DEGRADED)
    b = FACTOR.compute(snap(1, 10.0, atr=None), ctx)
    assert (b.score, b.quality) == (30.0, Quality.DEGRADED)
    assert "expected_1d_move" not in {e.name for e in b.evidence}


def test_unit_volatility_missing_direction_or_rank_is_missing(ctx: FactorContext) -> None:
    """TS-SCR-383: no direction (null or 0) or no band width rank -> missing, score 0."""
    for doc in (snap(None, 10.0), snap(0, 10.0), snap(1, None)):
        res = FACTOR.compute(doc, ctx)
        assert (res.score, res.quality) == (0.0, Quality.MISSING)


def test_unit_volatility_evidence_and_reasons_use_templates(ctx: FactorContext) -> None:
    """TS-SCR-384: rendered reasons for squeeze, expansion, against, extreme and the risk items."""
    sq = {e.name: e for e in FACTOR.compute(snap(1, 10.0, atr_rank=95.5), ctx).evidence}
    assert sq["squeeze"].reason == "Band width rank 10.00 is below 15: volatility is compressed"
    assert sq["atr_pct_rank"].reason == (
        "ATR rank 95.50 is above 90: the score is halved in extreme volatility"
    )
    assert sq["atr_pct"].reason == "ATR is 2.34 percent of the close"
    assert sq["hv20"].reason == "20-day historical volatility is 31.00 percent annualized"
    assert sq["bandwidth"].reason == "Bollinger band width is 12.00 percent of the average"
    ex = {
        e.name: e for e in FACTOR.compute(snap(1, 90.0, expansion=1.0, close=103.0), ctx).evidence
    }
    assert ex["expansion"].reason == (
        "Band width rank 90.00 is above 85 and rising, and the close moved with the trend"
    )
    ag = {e.name: e for e in FACTOR.compute(snap(1, 90.0, expansion=1.0, close=97.0), ctx).evidence}
    assert ag["expansion"].reason == (
        "Band width rank 90.00 is above 85 and rising, but the close moved against the trend"
    )
    quiet = {e.name: e for e in FACTOR.compute(snap(1, 50.0), ctx).evidence}
    assert quiet["bbw_rank"].reason == "Band width rank 50.00 is neither a squeeze nor an expansion"


def test_unit_volatility_on_real_snapshots_agrees_with_snapshot_flags(
    ctx: FactorContext, cfg: ScoringConfig
) -> None:
    """TS-SCR-385: computed snapshots: in range; the rank-derived squeeze equals the flag."""
    for seed in range(8):
        bundle = make_bundle(seed=seed, n=400, intraday_from=None)
        doc = compute_snapshot(bundle, cfg, date.fromisoformat(str(bundle.dates[-1])))
        d = doc["daily"]
        assert bool(d["squeeze"]) is (d["bbw_rank"] < 15)
        res = FACTOR.compute(doc, ctx)
        assert -100.0 <= res.score <= 100.0
        assert res.quality is Quality.OK
        direction = d["supertrend"]["direction"]
        expected = 0.0
        if d["bbw_rank"] < 15:
            expected = 30.0 * direction
        elif d["expansion"] and direction * (d["close"] - d["close_lag_3"]) > 0:
            expected = 20.0 * direction
        if d["atr_pct_rank"] > 90:
            expected *= 0.5
        assert res.score == pytest.approx(expected)
