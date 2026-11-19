# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 10, Buy / sell volume (Signal Engine Specification; FR-313; TEST_PLAN 10.4.10; S3-T04).

Expected values are derived by hand from the rule line:

    score = clip(delta_pct_10 * 300, -50, 50) + clip(cmf20 * 200, -50, 50)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from supertrends.scoring.config import ScoringConfig, load_scoring_config
from supertrends.scoring.factor import FactorContext, Quality, get_path
from supertrends.scoring.factors import flow
from supertrends.scoring.factors.flow import FACTOR

CONFIG = Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"


@pytest.fixture(scope="module")
def cfg() -> ScoringConfig:
    return load_scoring_config(CONFIG)


@pytest.fixture(scope="module")
def ctx(cfg: ScoringConfig) -> FactorContext:
    return FactorContext(config=cfg, as_of=date(2026, 11, 13))


def snap(
    delta: float | None,
    cmf: float | None,
    quality: str = "intraday",
    *,
    sessions: int = 10,
    acc: float | None = 3.0,
    dist: float | None = 1.0,
) -> dict[str, Any]:
    return {
        "flow": {
            "delta_pct_10": delta,
            "quality": quality,
            "daily_fallback": quality == "daily_estimate",
            "intraday_sessions": sessions,
        },
        "daily": {"cmf": cmf, "acc_dist": {"accumulation": acc, "distribution": dist}},
    }


# (delta_pct_10, cmf20, expected): clip(delta*300, +-50) + clip(cmf*200, +-50), by hand
SCORE_ROWS = [
    pytest.param(0.1, 0.2, 70.0, id="30+40-no-clip"),
    pytest.param(-0.1, -0.15, -60.0, id="-30-30-no-clip"),
    pytest.param(0.1, 0.3, 80.0, id="30+50-cmf-clipped-FR-313-example"),
    pytest.param(0.2, 0.0, 50.0, id="delta-60-clipped-to-50"),
    pytest.param(1.0, 1.0, 100.0, id="both-clipped-to-100"),
    pytest.param(-1.0, -1.0, -100.0, id="both-clipped-to-minus-100"),
    pytest.param(0.0, 0.25, 50.0, id="cmf-exactly-50"),
    pytest.param(0.0, 0.24, 48.0, id="cmf-48-not-clipped"),
    pytest.param(-0.25, 0.0, -50.0, id="delta-minus-75-clipped"),
    pytest.param(0.0, 0.0, 0.0, id="zero"),
    pytest.param(0.1, -0.1, 10.0, id="opposing-30-20"),
    pytest.param(-0.1, 0.1, -10.0, id="opposing-minus-30-plus-20"),
]


@pytest.mark.parametrize(("delta", "cmf", "expected"), SCORE_ROWS)
def test_ts_scr_150_delta_clip_50_plus_cmf_clip_50(
    ctx: FactorContext, delta: float, cmf: float, expected: float
) -> None:
    """TS-SCR-150: both parts and both clips, by hand per row."""
    assert FACTOR.compute(snap(delta, cmf), ctx).score == pytest.approx(expected)


def test_ts_scr_151_delta_pct_10_0_2_clipped_at_50(ctx: FactorContext) -> None:
    """TS-SCR-151: 0.2 * 300 = 60 clips to 50; 0.1667 * 300 = 50.01 also clips to 50."""
    assert FACTOR.compute(snap(0.2, 0.0), ctx).score == pytest.approx(50.0)
    assert FACTOR.compute(snap(0.1667, 0.0), ctx).score == pytest.approx(50.0)
    assert FACTOR.compute(snap(0.16, 0.0), ctx).score == pytest.approx(48.0)


def test_ts_scr_152_cmf20_negative_part_clipped_at_minus_50(ctx: FactorContext) -> None:
    """TS-SCR-152: -0.3 * 200 = -60 clips to -50; -0.25 is exactly -50; -0.2 is -40."""
    assert FACTOR.compute(snap(0.0, -0.3), ctx).score == pytest.approx(-50.0)
    assert FACTOR.compute(snap(0.0, -0.25), ctx).score == pytest.approx(-50.0)
    assert FACTOR.compute(snap(0.0, -0.2), ctx).score == pytest.approx(-40.0)


@pytest.mark.parametrize("quality", ["intraday", "trades"])
def test_ts_scr_153_quality_intraday_weight_multiplier_1_0(
    ctx: FactorContext, quality: str
) -> None:
    """TS-SCR-153: intraday (and trades) keep the full weight and quality ok."""
    result = FACTOR.compute(snap(0.1, 0.1, quality), ctx)
    assert result.weight_multiplier == 1.0
    assert result.quality is Quality.OK


def test_ts_scr_154_quality_daily_estimate_weight_multiplier_0_6(ctx: FactorContext) -> None:
    """TS-SCR-154: daily_estimate gives quality daily_estimate and multiplier 0.6 from config."""
    result = FACTOR.compute(snap(0.1, 0.1, "daily_estimate", sessions=3), ctx)
    assert result.quality is Quality.DAILY_ESTIMATE
    assert result.weight_multiplier == 0.6
    assert result.score == pytest.approx(50.0)  # 30 + 20, the score is not discounted


def test_ts_scr_154_multiplier_is_read_from_the_config(cfg: ScoringConfig) -> None:
    """TS-SCR-154: a changed flow.daily_estimate_weight_multiplier is used, not a literal 0.6."""
    changed = cfg.model_copy(
        update={"flow": cfg.flow.model_copy(update={"daily_estimate_weight_multiplier": 0.25})}
    )
    context = FactorContext(config=changed, as_of=date(2026, 11, 13))
    assert FACTOR.compute(snap(0.1, 0.1, "daily_estimate"), context).weight_multiplier == 0.25


@pytest.mark.parametrize("quality", ["intraday", "daily_estimate", "trades"])
def test_ts_scr_155_quality_stored_and_shown_in_evidence(
    ctx: FactorContext, quality: str
) -> None:
    """TS-SCR-155: a flow_quality item carries the snapshot quality and shows it in the reason."""
    result = FACTOR.compute(snap(0.1, 0.1, quality, sessions=7), ctx)
    item = {e.name: e for e in result.evidence}["flow_quality"]
    assert item.value == quality
    assert quality in item.reason
    sessions = {e.name: e for e in result.evidence}["intraday_sessions"]
    assert sessions.value == 7
    assert "7" in sessions.reason


def test_ts_scr_156_accumulation_distribution_days_reported_as_evidence(
    ctx: FactorContext,
) -> None:
    """TS-SCR-156: the 20-session counts (here 4 and 2) are evidence, with no effect on score."""
    result = FACTOR.compute(snap(0.1, 0.1, acc=4.0, dist=2.0), ctx)
    by_name = {e.name: e for e in result.evidence}
    assert by_name["accumulation_days"].value == 4
    assert by_name["distribution_days"].value == 2
    assert "4" in by_name["accumulation_days"].reason
    assert "2" in by_name["distribution_days"].reason
    assert result.score == FACTOR.compute(snap(0.1, 0.1, acc=0.0, dist=9.0), ctx).score


def test_ts_scr_157_trades_quality_path_accepts_provider_flag(ctx: FactorContext) -> None:
    """TS-SCR-157: quality `trades` (tick-rule upgrade) is accepted and scored like intraday."""
    trades = FACTOR.compute(snap(0.1, 0.2, "trades", sessions=0), ctx)
    intraday = FACTOR.compute(snap(0.1, 0.2, "intraday"), ctx)
    assert trades.score == intraday.score == pytest.approx(70.0)
    assert trades.quality is Quality.OK
    assert {e.name: e for e in trades.evidence}["flow_quality"].value == "trades"


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(snap(None, 0.2), id="delta-warm-up"),
        pytest.param(snap(0.1, None), id="cmf-warm-up"),
        pytest.param(snap(None, None, "daily_estimate"), id="both-warm-up"),
    ],
)
def test_ts_scr_405_null_input_is_missing_score_zero(
    ctx: FactorContext, bad: dict[str, Any]
) -> None:
    """TS-SCR-405: delta_pct_10 or cmf20 still in warm-up gives a missing factor, score 0."""
    result = FACTOR.compute(bad, ctx)
    assert result.quality is Quality.MISSING
    assert result.score == 0.0
    assert result.factor_id == "flow"
    assert result.evidence[0].name == "data_available"


def test_ts_scr_406_unknown_quality_is_rejected(ctx: FactorContext) -> None:
    """TS-SCR-406: a quality outside intraday, daily_estimate, trades is a programming error."""
    with pytest.raises(ValueError, match="quality"):
        FACTOR.compute(snap(0.1, 0.1, "bogus"), ctx)


def test_ts_scr_407_null_day_counts_leave_out_those_items(ctx: FactorContext) -> None:
    """TS-SCR-407: counts still in warm-up are left out of the evidence; the score is unchanged."""
    result = FACTOR.compute(snap(0.1, 0.2, acc=None, dist=None), ctx)
    names = {e.name for e in result.evidence}
    assert "accumulation_days" not in names
    assert "distribution_days" not in names
    assert result.score == pytest.approx(70.0)


def test_ts_scr_408_evidence_lists_delta_and_cmf_with_reasons(ctx: FactorContext) -> None:
    """TS-SCR-408: delta_pct_10 and cmf20 items carry the value and a reason with it formatted."""
    result = FACTOR.compute(snap(0.1, 0.2), ctx)
    by_name = {e.name: e for e in result.evidence}
    assert by_name["delta_pct_10"].value == 0.1
    assert by_name["cmf_20"].value == 0.2
    assert "0.10" in by_name["delta_pct_10"].reason
    assert "0.20" in by_name["cmf_20"].reason


def test_ts_scr_409_input_paths_resolve_and_factor_is_pure(ctx: FactorContext) -> None:
    """TS-SCR-409: declared paths resolve in a snapshot-shaped mapping; compute is pure."""
    s = snap(0.05, -0.1)
    for path in flow.INPUT_PATHS:
        get_path(s, path)
    before = repr(s)
    assert FACTOR.compute(s, ctx) == FACTOR.compute(s, ctx)
    assert repr(s) == before
    assert FACTOR.id == "flow"
