# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 9, Volume oscillator (Signal Engine Specification; FR-312; TEST_PLAN 10.4.9; S3-T04).

Expected values are derived by hand from the rule lines:

    vo_part  = clip(vo * 2, -60, 60) * sign(ret5)
    obv_part = 40 * obv_slope_sign
    score    = clip(vo_part + obv_part, -100, 100)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from supertrends.scoring.config import ScoringConfig, load_scoring_config
from supertrends.scoring.factor import FactorContext, Quality, get_path
from supertrends.scoring.factors import volume_osc
from supertrends.scoring.factors.volume_osc import FACTOR

CONFIG = Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"


@pytest.fixture(scope="module")
def cfg() -> ScoringConfig:
    return load_scoring_config(CONFIG)


@pytest.fixture(scope="module")
def ctx(cfg: ScoringConfig) -> FactorContext:
    return FactorContext(config=cfg, as_of=date(2026, 11, 13))


def snap(vo: float | None, ret5: float | None, obv: float | None) -> dict[str, Any]:
    return {"daily": {"volume_oscillator": vo, "ret_5": ret5, "obv_slope_sign": obv}}


def score(ctx: FactorContext, vo: float, ret5: float, obv: float) -> float:
    return FACTOR.compute(snap(vo, ret5, obv), ctx).score


def test_ts_scr_140_positive_vo_rising_price_vo_part_positive(ctx: FactorContext) -> None:
    """TS-SCR-140: vo=20, ret5>0, obv flat: vo_part = clip(40) * +1 = +40, obv_part 0."""
    assert score(ctx, 20.0, 0.03, 0.0) == pytest.approx(40.0)


def test_ts_scr_141_positive_vo_falling_price_vo_part_negative(ctx: FactorContext) -> None:
    """TS-SCR-141: vo=20, ret5<0, obv=-1: vo_part=-40, obv_part=-40, score=-80 (FR-312 example)."""
    result = FACTOR.compute(snap(20.0, -0.02, -1.0), ctx)
    assert result.score == pytest.approx(-80.0)
    assert result.quality is Quality.OK
    assert result.weight_multiplier == 1.0


def test_ts_scr_141_vo_part_alone_negative_on_a_falling_price(ctx: FactorContext) -> None:
    """TS-SCR-141: with a flat OBV the 20 vo on a falling price is exactly -40 (selling)."""
    assert score(ctx, 20.0, -0.02, 0.0) == pytest.approx(-40.0)


def test_ts_scr_142_negative_vo_rising_price_vo_part_negative(ctx: FactorContext) -> None:
    """TS-SCR-142: vo=-10, ret5>0: vo_part = -20 * +1 = -20 (rally on fading volume)."""
    assert score(ctx, -10.0, 0.01, 0.0) == pytest.approx(-20.0)


def test_ts_scr_143_negative_vo_falling_price_vo_part_positive(ctx: FactorContext) -> None:
    """TS-SCR-143: vo=-10, ret5<0: vo_part = -20 * -1 = +20 (decline on fading volume)."""
    assert score(ctx, -10.0, -0.01, 0.0) == pytest.approx(20.0)


# (vo, ret5, expected vo_part); obv flat. clip(vo*2, -60, 60) * sign(ret5)
CLIP_ROWS = [
    pytest.param(31.0, 0.01, 60.0, id="62-clips-to-60-up"),
    pytest.param(30.0, 0.01, 60.0, id="exactly-60-up"),
    pytest.param(29.0, 0.01, 58.0, id="58-not-clipped-up"),
    pytest.param(500.0, 0.01, 60.0, id="huge-clips-to-60-up"),
    pytest.param(-31.0, 0.01, -60.0, id="minus-62-clips-to-minus-60-up"),
    pytest.param(-30.0, 0.01, -60.0, id="exactly-minus-60-up"),
    pytest.param(-29.0, 0.01, -58.0, id="minus-58-not-clipped-up"),
    pytest.param(31.0, -0.01, -60.0, id="62-clips-to-60-down"),
    pytest.param(-31.0, -0.01, 60.0, id="minus-62-clips-to-minus-60-down"),
    pytest.param(-100.0, -0.01, 60.0, id="vo-minus-100-down"),
]


@pytest.mark.parametrize(("vo", "ret5", "expected"), CLIP_ROWS)
def test_ts_scr_144_vo_part_clipped_at_60(
    ctx: FactorContext, vo: float, ret5: float, expected: float
) -> None:
    """TS-SCR-144: clip(vo*2, -60, 60) * sign(ret5), by hand per row."""
    assert score(ctx, vo, ret5, 0.0) == pytest.approx(expected)


@pytest.mark.parametrize("vo", [20.0, -20.0, 0.0])
def test_ts_scr_145_ret5_zero_vo_part_zero(ctx: FactorContext, vo: float) -> None:
    """TS-SCR-145: sign(0) = 0 so vo_part is 0 whatever vo is; obv_part +40 remains."""
    assert score(ctx, vo, 0.0, 1.0) == pytest.approx(40.0)
    assert score(ctx, vo, 0.0, 0.0) == pytest.approx(0.0)


@pytest.mark.parametrize("ret5", [0.02, -0.02, 0.0])
def test_ts_scr_146_obv_slope_positive_adds_40(ctx: FactorContext, ret5: float) -> None:
    """TS-SCR-146: vo=0 gives vo_part 0, so the score is obv_part = 40 * +1."""
    assert score(ctx, 0.0, ret5, 1.0) == pytest.approx(40.0)


@pytest.mark.parametrize("ret5", [0.02, -0.02, 0.0])
def test_ts_scr_147_obv_slope_negative_subtracts_40(ctx: FactorContext, ret5: float) -> None:
    """TS-SCR-147: vo=0 gives vo_part 0, so the score is obv_part = 40 * -1."""
    assert score(ctx, 0.0, ret5, -1.0) == pytest.approx(-40.0)


# (vo, ret5, obv, expected): 60 + 40 is the largest reachable sum, so the clip is a guard
TOTAL_ROWS = [
    pytest.param(30.0, 0.01, 1.0, 100.0, id="60+40=100-boundary"),
    pytest.param(100.0, 0.01, 1.0, 100.0, id="vo-clipped-then-100"),
    pytest.param(30.0, -0.01, -1.0, -100.0, id="-60-40=-100-boundary"),
    pytest.param(-100.0, 0.01, -1.0, -100.0, id="down-side-minus-100"),
    pytest.param(30.0, 0.01, -1.0, 20.0, id="60-40=20-opposing-parts"),
    pytest.param(-30.0, 0.01, 1.0, -20.0, id="-60+40=-20"),
]


@pytest.mark.parametrize(("vo", "ret5", "obv", "expected"), TOTAL_ROWS)
def test_ts_scr_148_total_clipped_to_100(
    ctx: FactorContext, vo: float, ret5: float, obv: float, expected: float
) -> None:
    """TS-SCR-148: score = clip(vo_part + obv_part, -100, 100), by hand per row."""
    assert score(ctx, vo, ret5, obv) == pytest.approx(expected)


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(snap(None, 0.01, 1.0), id="vo-warm-up"),
        pytest.param(snap(20.0, None, 1.0), id="ret5-warm-up"),
        pytest.param(snap(20.0, 0.01, None), id="obv-warm-up"),
    ],
)
def test_ts_scr_400_null_input_is_missing_score_zero(
    ctx: FactorContext, bad: dict[str, Any]
) -> None:
    """TS-SCR-400: an input still in warm-up gives a missing factor: score 0, one data flag."""
    result = FACTOR.compute(bad, ctx)
    assert result.quality is Quality.MISSING
    assert result.score == 0.0
    assert result.factor_id == "volume_osc"
    assert result.evidence[0].name == "data_available"
    assert result.evidence[0].value is False


def test_ts_scr_401_evidence_lists_inputs_and_parts_with_reasons(ctx: FactorContext) -> None:
    """TS-SCR-401: vo=20, ret5=-0.02, obv=-1 gives items vo, ret5, obv slope, with the parts."""
    result = FACTOR.compute(snap(20.0, -0.02, -1.0), ctx)
    by_name = {e.name: e for e in result.evidence}
    assert by_name["volume_oscillator"].value == 20.0
    assert by_name["ret_5"].value == -0.02
    assert by_name["obv_slope_sign"].value == -1
    assert by_name["vo_part"].value == -40.0
    assert by_name["obv_part"].value == -40.0
    assert "20.00" in by_name["volume_oscillator"].reason
    assert "-40.00" in by_name["vo_part"].reason
    assert all(e.reason for e in result.evidence)


def test_ts_scr_402_reasons_name_the_direction_of_the_volume_signal(ctx: FactorContext) -> None:
    """TS-SCR-402: the vo_part reason says whether volume confirms or fades the 5-bar move."""
    confirm = FACTOR.compute(snap(20.0, 0.02, 0.0), ctx)
    fade = FACTOR.compute(snap(-20.0, 0.02, 0.0), ctx)
    assert "confirm" in {e.name: e for e in confirm.evidence}["vo_part"].reason
    assert "fade" in {e.name: e for e in fade.evidence}["vo_part"].reason


def test_ts_scr_403_input_paths_exist_in_declared_list_and_are_read(ctx: FactorContext) -> None:
    """TS-SCR-403: every declared input path resolves in a snapshot-shaped mapping."""
    s = snap(1.0, 0.01, 1.0)
    for path in volume_osc.INPUT_PATHS:
        assert get_path(s, path) is not None
    assert FACTOR.id == "volume_osc"
    assert FACTOR.input_paths == volume_osc.INPUT_PATHS


def test_ts_scr_404_pure_and_deterministic(ctx: FactorContext) -> None:
    """TS-SCR-404: the same snapshot gives equal results and the snapshot is not mutated."""
    s = snap(12.5, -0.013, 1.0)
    before = repr(s)
    assert FACTOR.compute(s, ctx) == FACTOR.compute(s, ctx)
    assert repr(s) == before
