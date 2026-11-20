# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 5, Mean reversion (S3-T03; BUILD_PROMPT Factor 5; PRD FR-307; TEST_PLAN 10.4.5).

Defaults: z_cap 2.5, RSI bounds 30 and 70, so `z_part = -60 * clip(z / 2.5, -1, 1)` and
`rsi_part = 40 - 80 * (rsi - 30) / 40 = 40 - 2 * (rsi - 30)` between the bounds. Every expected
value below is worked by hand in the row comment.
"""

from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from supertrends.indicators.meanrev import zscore
from supertrends.scoring.config import ScoringConfig, load_scoring_config
from supertrends.scoring.factor import FactorContext, Quality
from supertrends.scoring.factors.mean_reversion import FACTOR
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
    z: float | None = 0.0,
    rsi: float | None = 50.0,
    pct_b: float | None = 0.5,
    close: float = 100.0,
) -> dict[str, Any]:
    return {"daily": {"zscore": z, "rsi": rsi, "pct_b": pct_b, "close": close}}


def test_unit_mean_reversion_score_z_plus_2_5_z_part_minus_60(ctx: FactorContext) -> None:
    """TS-SCR-090: stretched up is bearish: z 2.5, RSI 50 -> -60 + 0."""
    res = FACTOR.compute(snap(z=2.5), ctx)
    assert res.score == -60.0  # z/2.5 = 1 -> -60; rsi_part = 40 - 2*20 = 0
    assert res.quality is Quality.OK


def test_unit_mean_reversion_score_z_minus_2_5_z_part_plus_60(ctx: FactorContext) -> None:
    """TS-SCR-091: stretched down is bullish: z -2.5, RSI 50 -> +60 + 0."""
    assert FACTOR.compute(snap(z=-2.5), ctx).score == 60.0


@pytest.mark.parametrize(
    ("z", "expected"),
    [
        (2.5000001, -60.0),  # just past the cap: clip(1.0000000x) = 1 -> -60
        (3.5, -60.0),  # 3.5/2.5 = 1.4 -> clipped to 1 -> -60
        (-3.5, 60.0),  # mirror
        (1.25, -30.0),  # 1.25/2.5 = 0.5 -> -30 (inside the cap, no clipping)
        (-1.25, 30.0),
    ],
)
def test_unit_mean_reversion_score_z_beyond_2_5_clipped_at_60(
    ctx: FactorContext, z: float, expected: float
) -> None:
    """TS-SCR-092: `clip(z/2.5, -1, 1)` bounds the z part at 60."""
    assert FACTOR.compute(snap(z=z), ctx).score == pytest.approx(expected)


def test_unit_mean_reversion_score_z_zero_z_part_zero(ctx: FactorContext) -> None:
    """TS-SCR-093: z 0 and RSI 50 is neutral: 0 + 0."""
    res = FACTOR.compute(snap(z=0.0, rsi=50.0), ctx)
    assert res.score == 0.0
    assert str(res.score) == "0.0"  # no negative zero


def test_unit_mean_reversion_score_rsi_30_rsi_part_plus_40(ctx: FactorContext) -> None:
    """TS-SCR-094: RSI exactly 30 -> +40 (z 0)."""
    assert FACTOR.compute(snap(rsi=30.0), ctx).score == 40.0


def test_unit_mean_reversion_score_rsi_70_rsi_part_minus_40(ctx: FactorContext) -> None:
    """TS-SCR-095: RSI exactly 70 -> -40 (z 0)."""
    assert FACTOR.compute(snap(rsi=70.0), ctx).score == -40.0


@pytest.mark.parametrize(
    ("rsi", "expected"),
    [
        (50.0, 0.0),  # midpoint: 40 - 2*(50-30) = 0
        (40.0, 20.0),  # 40 - 2*10
        (60.0, -20.0),  # 40 - 2*30
        (35.0, 30.0),  # 40 - 2*5
        (65.0, -30.0),  # 40 - 2*35
    ],
)
def test_unit_mean_reversion_score_rsi_50_rsi_part_zero_linear_midpoint(
    ctx: FactorContext, rsi: float, expected: float
) -> None:
    """TS-SCR-096: linear from +40 at 30 to -40 at 70, zero at 50 (z 0)."""
    assert FACTOR.compute(snap(rsi=rsi), ctx).score == pytest.approx(expected)


@pytest.mark.parametrize(
    ("rsi", "expected"),
    [(29.99, 40.0), (20.0, 40.0), (0.0, 40.0), (70.01, -40.0), (85.0, -40.0), (100.0, -40.0)],
)
def test_unit_mean_reversion_score_rsi_below_30_stays_plus_40(
    ctx: FactorContext, rsi: float, expected: float
) -> None:
    """TS-SCR-097: no overshoot past the RSI bounds (z 0); the high side mirrors it."""
    # 29.99 -> linear value would be 40.02, clipped to 40; 70.01 -> -40.02, clipped to -40
    assert FACTOR.compute(snap(rsi=rsi), ctx).score == pytest.approx(expected)


@pytest.mark.parametrize("pct_b", [None, 0.0, 0.5, 1.0, 1.7, -0.3])
def test_unit_mean_reversion_score_pct_b_is_evidence_only_not_in_score(
    ctx: FactorContext, pct_b: float | None
) -> None:
    """TS-SCR-098: `pct_b` does not change the score (z 1.25 -> -30, RSI 60 -> -20 = -50)."""
    res = FACTOR.compute(snap(z=1.25, rsi=60.0, pct_b=pct_b), ctx)
    assert res.score == pytest.approx(-50.0)
    assert ("pct_b" in {e.name for e in res.evidence}) is (pct_b is not None)


def test_unit_mean_reversion_score_stdev_zero_flat_series_returns_zero_degraded(
    ctx: FactorContext,
) -> None:
    """TS-SCR-099: zero standard deviation (null z-score) is handled without error."""
    # Hand-made: z null, RSI 50 -> rsi_part 0, z_part 0 -> score 0, degraded.
    res = FACTOR.compute(snap(z=None, rsi=50.0), ctx)
    assert res.score == 0.0
    assert res.quality is Quality.DEGRADED
    # The indicator itself returns NaN (null in the snapshot) on a perfectly flat series.
    assert np.isnan(zscore(np.full(60, 100.0), 20)[-1])


@pytest.mark.parametrize(
    ("z", "rsi", "expected"),
    [
        (-2.5, 20.0, 100.0),  # +60 + 40 = 100 (the maximum, not past it)
        (2.5, 80.0, -100.0),  # -60 - 40
        (1.25, 60.0, -50.0),  # -30 - 20
        (-1.25, 40.0, 50.0),  # +30 + 20
        (2.5, 70.0, -100.0),  # FR-307 example: -60 - 40
        (2.5, 30.0, -20.0),  # -60 + 40: the two parts oppose
        (-2.5, 70.0, 20.0),  # +60 - 40
    ],
)
def test_unit_mean_reversion_score_parts_sum(
    ctx: FactorContext, z: float, rsi: float, expected: float
) -> None:
    """TS-SCR-360: the score is z_part + rsi_part, both signs and both parts opposing."""
    assert FACTOR.compute(snap(z=z, rsi=rsi), ctx).score == pytest.approx(expected)


def test_unit_mean_reversion_evidence_and_reasons_use_templates(ctx: FactorContext) -> None:
    """TS-SCR-361: evidence names, units and rendered reasons (2-decimal numbers)."""
    res = FACTOR.compute(snap(z=1.234, rsi=61.5, pct_b=0.8765), ctx)
    by_name = {e.name: e for e in res.evidence}
    assert set(by_name) == {"zscore", "rsi", "pct_b", "z_part", "rsi_part"}
    assert by_name["zscore"].value == 1.234
    assert by_name["zscore"].reason == "Close is 1.23 standard deviations from its 20-day average"
    assert by_name["rsi"].reason == "RSI(14) is 61.50"
    assert by_name["pct_b"].reason == "Close sits at 0.88 of the Bollinger band width"
    # z_part = -60 * 1.234/2.5 = -29.616 ; rsi_part = 40 - 2*(61.5-30) = -23
    assert by_name["z_part"].reason == "Stretch from the average contributes -29.62 points"
    assert by_name["rsi_part"].reason == "RSI contributes -23.00 points"
    assert res.score == pytest.approx(-52.616)


def test_unit_mean_reversion_null_inputs_degrade_or_go_missing(ctx: FactorContext) -> None:
    """TS-SCR-362: one null input degrades the factor; both null make it missing."""
    only_z = FACTOR.compute(snap(z=-1.25, rsi=None), ctx)
    assert (only_z.score, only_z.quality) == (30.0, Quality.DEGRADED)  # +30 from z, rsi 0
    only_rsi = FACTOR.compute(snap(z=None, rsi=30.0), ctx)
    assert (only_rsi.score, only_rsi.quality) == (40.0, Quality.DEGRADED)
    neither = FACTOR.compute(snap(z=None, rsi=None), ctx)
    assert (neither.score, neither.quality) == (0.0, Quality.MISSING)
    assert neither.evidence[0].name == "data_available"


def test_unit_mean_reversion_on_real_snapshots_is_in_range_and_declares_inputs(
    ctx: FactorContext, cfg: ScoringConfig
) -> None:
    """TS-SCR-363: computed snapshots score within -100..100 with ok quality, no NaN."""
    assert FACTOR.id == "mean_reversion"
    for seed in range(5):
        bundle = make_bundle(seed=seed, n=400, intraday_from=None)
        doc = compute_snapshot(bundle, cfg, date.fromisoformat(str(bundle.dates[-1])))
        res = FACTOR.compute(doc, ctx)
        assert res.factor_id == "mean_reversion"
        assert -100.0 <= res.score <= 100.0
        assert res.quality is Quality.OK
        # independent: recompute the z part from the snapshot's own z-score
        z = doc["daily"]["zscore"]
        rsi = doc["daily"]["rsi"]
        z_part = -60.0 * max(-1.0, min(1.0, z / 2.5))
        rsi_part = max(-40.0, min(40.0, 40.0 - 2.0 * (rsi - 30.0)))
        assert res.score == pytest.approx(z_part + rsi_part)
