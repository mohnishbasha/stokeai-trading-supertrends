# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Snapshot completeness for the factor rules (S3-T01 audit of the Signal Engine Specification).

Every input a rule line of Factors 1 to 10 and 12, the confidence rule, the regime rule and the
selection gate reads is declared as a snapshot path by its factor module (`INPUT_PATHS`) or in
`supertrends.scoring.factor`. These tests walk the declared paths against a computed snapshot, so
the factor tasks (S3-T02, S3-T03, S3-T04, S3-T14) and the composite, confidence and selection
tasks can rely on them, and check the new fields against independent numpy computations.
"""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from supertrends.indicators.registry import Bundle
from supertrends.scoring.config import (
    FACTOR_IDS,
    ScoringConfig,
    load_scoring_config,
    parse_scoring_config,
)
from supertrends.scoring.factor import (
    CONFIDENCE_INPUT_PATHS,
    REGIME_INPUT_PATHS,
    SELECTION_INPUT_PATHS,
    expand_input_paths,
    get_path,
)
from supertrends.scoring.factors import default_registry
from supertrends.scoring.snapshot import (
    NOT_SNAPSHOTTED,
    SCHEMA_VERSION,
    SNAPSHOT_COVERS,
    compute_snapshot,
)
from tests.unit.indicators.lookahead_support import make_bundle

CONFIG = Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"
N = 420

# Paths whose value is legitimately null on some data (no cross in the window, no qualifying leg,
# stack 0 so no flip count, no level on a side). Everything else must be a real value.
NULLABLE = {
    "daily.sma_cross",
    "daily.macd_cross",
    "fib.leg",
    "ripster.bars_since_stack_flip",
    "levels.support_resistance.nearest_support",
    "levels.support_resistance.nearest_resistance",
    "levels.support_resistance.d_s",
    "levels.support_resistance.d_r",
}


@pytest.fixture(scope="module")
def cfg() -> ScoringConfig:
    return load_scoring_config(CONFIG)


@pytest.fixture(scope="module")
def bundle() -> Bundle:
    return make_bundle(seed=7, n=N, intraday_from=N - 20)


@pytest.fixture(scope="module")
def doc(bundle: Bundle, cfg: ScoringConfig) -> dict[str, Any]:
    return compute_snapshot(bundle, cfg, date.fromisoformat(str(bundle.dates[-1])))


def _paths_of(factor_id: str, cfg: ScoringConfig) -> tuple[str, ...]:
    return expand_input_paths(default_registry().get(factor_id).input_paths, cfg)


@pytest.mark.parametrize("factor_id", [f for f in FACTOR_IDS if f != "fundamentals"])
def test_unit_snapshot_contains_every_input_path_of_the_factor(
    factor_id: str, doc: dict[str, Any], cfg: ScoringConfig
) -> None:
    """TS-SCR-310: every declared input of the factor exists in the snapshot, non-null unless
    the value is legitimately absent on some data."""
    paths = _paths_of(factor_id, cfg)
    assert paths, f"{factor_id} declares no input paths"
    for path in paths:
        value = get_path(doc, path)  # KeyError names the missing path
        if path not in NULLABLE:
            assert value is not None, path


def test_unit_snapshot_fundamentals_declares_no_snapshot_inputs(cfg: ScoringConfig) -> None:
    """TS-SCR-310: fundamentals come from the data layer through the context, not the snapshot."""
    assert default_registry().get("fundamentals").input_paths == ()


@pytest.mark.parametrize(
    "paths",
    [REGIME_INPUT_PATHS, CONFIDENCE_INPUT_PATHS, SELECTION_INPUT_PATHS],
    ids=["regime", "confidence", "selection"],
)
def test_unit_snapshot_contains_regime_confidence_and_selection_inputs(
    paths: tuple[str, ...], doc: dict[str, Any], cfg: ScoringConfig
) -> None:
    """TS-SCR-319: ADX, the confidence deductions and the selection gate inputs are present."""
    assert paths
    for path in expand_input_paths(paths, cfg):
        assert get_path(doc, path) is not None, path


def test_unit_snapshot_declared_input_lists_name_the_spec_inputs() -> None:
    """TS-SCR-319: the shared lists hold the spec's inputs (hand-listed from the rule text)."""
    assert REGIME_INPUT_PATHS == ("daily.adx.adx",)
    assert set(CONFIDENCE_INPUT_PATHS) == {
        "daily.atr_pct_rank",  # - 15 if atr_pct_rank > 90
        "daily.supertrend.direction",  # st_dir_d
        "weekly.supertrend_direction",  # - 10 if st_dir_w != st_dir_d
        "ripster.stack",  # - 10 if rc_stack == -st_dir_d
    }
    assert set(SELECTION_INPUT_PATHS) == {
        "daily.supertrend.direction",  # st_dir_d == +1 / -1
        "ripster.bias",  # rc_bias >= 0 / <= 0
        "daily.avg_dollar_volume_20d",  # liquidity floor
        "daily.relative_volume",  # ranking tie-breaker
        "daily.bars_since_flip",  # ranking tie-breaker
    }


@pytest.mark.parametrize("factor_id", FACTOR_IDS)
def test_unit_factor_module_docstring_lists_every_input_path(factor_id: str) -> None:
    """TS-SCR-316: the stub docstring tells the owning task where every input lives."""
    module = importlib.import_module(f"supertrends.scoring.factors.{factor_id}")
    doc_text = module.__doc__ or ""
    for path in module.INPUT_PATHS:
        assert f"`{path}`" in doc_text, f"{factor_id}: {path} missing from the docstring"


def test_unit_snapshot_new_daily_fields_match_independent_computations(
    doc: dict[str, Any], bundle: Bundle
) -> None:
    """TS-SCR-311: prev_close, high, low, close_lag_3, ret_5, avg_dollar_volume_20d."""
    c, h, lo, v = bundle.close, bundle.high, bundle.low, bundle.volume
    d = doc["daily"]
    assert d["high"] == pytest.approx(h[-1], rel=1e-9)
    assert d["low"] == pytest.approx(lo[-1], rel=1e-9)
    assert d["prev_close"] == pytest.approx(c[-2], rel=1e-9)
    assert d["close_lag_3"] == pytest.approx(c[-4], rel=1e-9)  # close 3 bars before the last
    assert d["ret_5"] == pytest.approx(c[-1] / c[-6] - 1.0, rel=1e-9)
    assert d["avg_dollar_volume_20d"] == pytest.approx(float((c[-20:] * v[-20:]).mean()), rel=1e-9)


def test_unit_snapshot_new_daily_fields_are_null_not_zero_in_warmup(cfg: ScoringConfig) -> None:
    """TS-SCR-311: too few bars gives null for the lagged fields and the 20-day average."""
    short = make_bundle(seed=3, n=4, intraday_from=None)
    d = compute_snapshot(short, cfg, date.fromisoformat(str(short.dates[-1])))["daily"]
    assert d["ret_5"] is None  # needs 6 closes
    assert d["avg_dollar_volume_20d"] is None  # needs 20 bars
    assert d["close_lag_3"] == pytest.approx(short.close[0], rel=1e-9)
    assert d["prev_close"] == pytest.approx(short.close[2], rel=1e-9)
    one = make_bundle(seed=3, n=1, intraday_from=None)
    first = compute_snapshot(one, cfg, date.fromisoformat(str(one.dates[-1])))["daily"]
    assert first["prev_close"] is None
    assert first["close_lag_3"] is None


def _sma(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for t in range(n - 1, len(x)):
        out[t] = x[t - n + 1 : t + 1].mean()
    return out


def _expected_cross(c: np.ndarray, lookback: int) -> int | None:
    """Direction of the latest SMA50 vs SMA200 cross among the last `lookback` bars."""
    fast, slow = _sma(c, 50), _sma(c, 200)
    for t in range(len(c) - 1, len(c) - 1 - lookback, -1):
        if t < 1 or np.isnan(slow[t - 1]):
            continue
        if fast[t - 1] <= slow[t - 1] and fast[t] > slow[t]:
            return 1
        if fast[t - 1] >= slow[t - 1] and fast[t] < slow[t]:
            return -1
    return None


def test_unit_snapshot_sma_cross_is_sma50_against_sma200_over_the_config_lookback(
    bundle: Bundle, cfg: ScoringConfig
) -> None:
    """TS-SCR-312: golden / death cross is SMA50 vs SMA200 (Factor 2), not SMA20 vs SMA50."""
    seen: set[int | None] = set()
    for end in range(230, N + 1, 3):
        part = bundle.head(end)
        got = compute_snapshot(part, cfg, date.fromisoformat(str(part.dates[-1])))["daily"]
        expected = _expected_cross(part.close, cfg.sma.cross_lookback)
        actual = None if got["sma_cross"] is None else got["sma_cross"]["direction"]
        assert actual == expected, end
        seen.add(expected)
    assert {1, -1} & seen, "the fixture never crosses; pick another seed"


def _ema(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    out[n - 1] = x[:n].mean()
    for t in range(n, len(x)):
        out[t] = out[t - 1] + (2.0 / (n + 1)) * (x[t] - out[t - 1])
    return out


def _cloud(src: np.ndarray, close: np.ndarray, s: int, lg: int) -> dict[str, np.ndarray]:
    a, b = _ema(src, s), _ema(src, lg)
    top, bot = np.maximum(a, b), np.minimum(a, b)
    pos = np.where(close > top, 1, np.where(close < bot, -1, 0))
    return {"top": top, "bot": bot, "dir": np.where(a > b, 1, -1), "pos": pos}


def test_unit_snapshot_ripster_block_matches_independent_ema_clouds(
    doc: dict[str, Any], bundle: Bundle, cfg: ScoringConfig
) -> None:
    """TS-SCR-313: every cloud's top, bot, dir and pos, plus bias, stack and c3 levels."""
    src = (bundle.high + bundle.low) / 2.0
    pairs = cfg.ripster.clouds.pairs()
    clouds = [_cloud(src, bundle.close, s, lg) for s, lg in pairs]
    block = doc["ripster"]
    for i, cloud in enumerate(clouds, start=1):
        got = block["clouds"][f"c{i}"]
        assert got["top"] == pytest.approx(cloud["top"][-1], rel=1e-9), i
        assert got["bot"] == pytest.approx(cloud["bot"][-1], rel=1e-9), i
        assert got["dir"] == cloud["dir"][-1], i
        assert got["pos"] == cloud["pos"][-1], i
    c2, c3 = clouds[1], clouds[2]
    stack = np.where(c2["bot"] > c3["top"], 1, np.where(c2["top"] < c3["bot"], -1, 0))
    assert block["stack"] == stack[-1]
    assert block["bias"] == c3["pos"][-1]
    assert block["c2_dir"] == c2["dir"][-1]
    assert block["c3_dir"] == c3["dir"][-1]
    assert block["c3_top"] == pytest.approx(c3["top"][-1], rel=1e-9)
    assert block["c3_bot"] == pytest.approx(c3["bot"][-1], rel=1e-9)
    assert block["dir_w"] in (1, -1)


def test_unit_snapshot_ripster_bars_since_stack_flip_and_pullback_match_independent_loops(
    doc: dict[str, Any], bundle: Bundle, cfg: ScoringConfig
) -> None:
    """TS-SCR-313: bars since the stack last changed, and the 8/9 pullback state (3-bar window)."""
    src = (bundle.high + bundle.low) / 2.0
    pairs = cfg.ripster.clouds.pairs()
    c1, c2, c3 = (_cloud(src, bundle.close, *pairs[i]) for i in (0, 1, 2))
    stack = np.where(c2["bot"] > c3["top"], 1, np.where(c2["top"] < c3["bot"], -1, 0))
    t = N - 1
    block = doc["ripster"]
    if stack[t] == 0:
        assert block["bars_since_stack_flip"] is None
    else:
        k = t
        while k > 0 and stack[k - 1] == stack[t]:
            k -= 1
        assert block["bars_since_stack_flip"] == t - k
    lb = cfg.ripster.pullback_lookback_bars
    window = range(t - lb + 1, t + 1)
    if stack[t] == 1:
        held = any(bundle.low[j] <= c1["top"][j] for j in window) and bundle.close[t] > c1["bot"][t]
        expected = 1 if held else 0
    elif stack[t] == -1:
        held = (
            any(bundle.high[j] >= c1["bot"][j] for j in window) and bundle.close[t] < c1["top"][t]
        )
        expected = -1 if held else 0
    else:
        expected = 0
    assert block["pullback"] == expected


def test_unit_snapshot_ripster_pullback_uses_the_configured_lookback(
    bundle: Bundle, cfg: ScoringConfig
) -> None:
    """TS-SCR-313: the snapshot reads `ripster.pullback_lookback_bars`; a wider window can only
    keep or add held pullbacks. Checked over many as-of dates."""
    raw = cfg.model_dump(mode="json")
    raw["ripster"]["pullback_lookback_bars"] = 30
    wide = parse_scoring_config(raw)
    more = 0
    for end in range(230, N + 1, 5):
        part = bundle.head(end)
        as_of = date.fromisoformat(str(part.dates[-1]))
        a = compute_snapshot(part, cfg, as_of)["ripster"]["pullback"]
        b = compute_snapshot(part, wide, as_of)["ripster"]["pullback"]
        assert abs(b) >= abs(a)
        more += abs(b) > abs(a)
    assert more > 0, "the wider window never changed anything; the test proves nothing"


def test_unit_snapshot_ripster_values_are_null_not_zero_in_warmup(cfg: ScoringConfig) -> None:
    """TS-SCR-313: with 60 bars the 180/200 cloud and the weekly direction are null, never 0."""
    short = make_bundle(seed=3, n=60, intraday_from=None)
    block = compute_snapshot(short, cfg, date.fromisoformat(str(short.dates[-1])))["ripster"]
    assert block["clouds"]["c5"]["top"] is None
    assert block["clouds"]["c5"]["pos"] is None
    assert block["clouds"]["c4"]["top"] is None  # the 89 EMA needs 89 bars
    assert block["clouds"]["c3"]["top"] is not None  # the 50 EMA is defined from bar 50
    assert block["dir_w"] is None
    assert block["clouds"]["c1"]["top"] is not None
    assert block["clouds"]["c2"]["dir"] in (1, -1)


def test_unit_snapshot_schema_version_is_2_and_ripster_is_covered() -> None:
    """TS-SCR-313: the document gained fields, so its schema number moved; ripster is covered."""
    assert SCHEMA_VERSION == 2
    for name in (
        "bars_since_stack_flip",
        "cloud_stack",
        "ripster_clouds",
        "ripster_pullback",
        "ripster_weekly_direction",
    ):
        assert name in SNAPSHOT_COVERS, name
        assert name not in NOT_SNAPSHOTTED, name
        assert SNAPSHOT_COVERS[name].startswith("ripster.")
