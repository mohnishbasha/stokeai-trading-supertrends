# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Indicator snapshot compute-all (TS-IND-096, 250 to 255; S2-T09)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from supertrends.indicators.registry import REGISTRY, Bundle, round_significant
from supertrends.scoring.config import (
    ScoringConfig,
    config_hash,
    load_scoring_config,
    parse_scoring_config,
)
from supertrends.scoring.snapshot import (
    NOT_SNAPSHOTTED,
    SNAPSHOT_COVERS,
    compute_snapshot,
    snapshot_bytes,
)
from tests.unit.indicators.lookahead_support import make_bundle

CONFIG = Path(__file__).parents[2] / "config" / "scoring.yaml"
N = 420


@pytest.fixture(scope="module")
def cfg() -> ScoringConfig:
    return load_scoring_config(CONFIG)


@pytest.fixture(scope="module")
def bundle() -> Bundle:
    return make_bundle(seed=7, n=N, intraday_from=N - 20)


def _date(bundle: Bundle, i: int) -> date:
    return date.fromisoformat(str(bundle.dates[i]))


def _scan(obj: object, path: str = "") -> list[tuple[str, object]]:
    """Every leaf of a JSON document with its path."""
    if isinstance(obj, dict):
        return [leaf for k, v in obj.items() for leaf in _scan(v, f"{path}.{k}")]
    if isinstance(obj, list):
        return [leaf for i, v in enumerate(obj) for leaf in _scan(v, f"{path}[{i}]")]
    return [(path, obj)]


def test_unit_snapshot_has_daily_weekly_levels_fib_divergence_flow_sections(
    bundle: Bundle, cfg: ScoringConfig
) -> None:
    """TS-IND-250: the document carries every section and the daily and weekly values."""
    doc = compute_snapshot(bundle, cfg, _date(bundle, N - 1))
    assert {"schema", "as_of", "bar_date", "bars", "config_hash"} <= doc.keys()
    assert {"daily", "weekly", "levels", "fib", "divergences", "flow"} <= doc.keys()
    assert doc["config_hash"] == config_hash(cfg)
    assert doc["bars"] == N
    assert doc["bar_date"] == str(bundle.dates[N - 1])
    for key in ("sma_20", "sma_50", "sma_200", "rsi", "atr", "adx", "macd", "supertrend"):
        assert key in doc["daily"], key
    # independent check: SMA(200) is the plain mean of the last 200 closes
    assert doc["daily"]["sma_200"] == pytest.approx(float(bundle.close[N - 200 :].mean()), rel=1e-9)
    assert {"supertrend_direction", "macd", "rsi"} <= doc["weekly"].keys()
    assert doc["levels"]["high_52w"] == pytest.approx(float(bundle.high[N - 252 :].max()), rel=1e-9)
    assert doc["levels"]["low_52w"] == pytest.approx(float(bundle.low[N - 252 :].min()), rel=1e-9)
    assert doc["levels"]["invalidation"] == doc["daily"]["supertrend"]["line"]
    assert {"daily", "weekly"} <= doc["divergences"].keys()
    assert doc["flow"]["quality"] in {"intraday", "daily_estimate", "trades"}


def test_unit_indicators_nan_warmup_never_leaks_as_zero_into_snapshot(
    cfg: ScoringConfig,
) -> None:
    """TS-IND-096: indicators still in warm-up are null, never 0, and the bytes are strict JSON."""
    short = make_bundle(seed=3, n=60, intraday_from=None)
    doc = compute_snapshot(short, cfg, _date(short, 59))
    assert doc["daily"]["sma_200"] is None
    assert doc["daily"]["supertrend"]["line"] is not None  # ATR(10) is ready at 60 bars
    assert doc["daily"]["atr_pct_rank"] is None  # needs 252 bars
    assert doc["levels"]["high_52w"] is not None  # a partial window is still a real maximum
    raw = snapshot_bytes(doc)
    assert b"NaN" not in raw
    assert b"Infinity" not in raw
    assert json.loads(raw)["daily"]["sma_200"] is None
    for path, value in _scan(doc["daily"]):
        if path.endswith(("sma_200", "atr_pct_rank")):
            assert value is None, path


def test_unit_snapshot_as_of_t_is_identical_with_or_without_later_bars(
    bundle: Bundle, cfg: ScoringConfig
) -> None:
    """TS-IND-251: bars after t, real or perturbed, change nothing in the snapshot at t."""
    other = make_bundle(seed=99, n=N, sigma=0.05, intraday_from=N - 20)
    for t in (300, 360, N - 30):
        as_of = _date(bundle, t)
        truncated = snapshot_bytes(compute_snapshot(bundle.head(t + 1), cfg, as_of))
        full = snapshot_bytes(compute_snapshot(bundle, cfg, as_of))
        perturbed = snapshot_bytes(compute_snapshot(bundle.with_tail(t + 1, other), cfg, as_of))
        assert truncated == full == perturbed, t


def test_unit_snapshot_json_bytes_are_deterministic_sorted_and_rounded(
    bundle: Bundle, cfg: ScoringConfig
) -> None:
    """TS-IND-252: same inputs, same bytes; sorted keys; floats at 10 significant digits."""
    as_of = _date(bundle, N - 1)
    first = snapshot_bytes(compute_snapshot(bundle, cfg, as_of))
    assert first == snapshot_bytes(compute_snapshot(bundle, cfg, as_of))
    parsed: dict[str, Any] = json.loads(first)
    assert list(parsed) == sorted(parsed)
    assert (
        first
        == json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    )
    for path, value in _scan(parsed):
        if isinstance(value, float):
            assert value == round_significant(value), path
    assert round_significant(1.23456789012345) == 1.23456789
    assert round_significant({"a": [0.1 + 0.2, 7, None, "x"]}) == {"a": [0.3, 7, None, "x"]}


def test_unit_snapshot_covers_every_registered_series_indicator() -> None:
    """TS-IND-253: each registry series entry is in the snapshot or listed with a reason."""
    series = {n for n, e in REGISTRY.items() if e.series is not None}
    assert series <= set(SNAPSHOT_COVERS) | set(NOT_SNAPSHOTTED)
    assert not set(SNAPSHOT_COVERS) & set(NOT_SNAPSHOTTED)
    assert all(NOT_SNAPSHOTTED.values())


def test_unit_snapshot_uses_parameters_from_the_config(bundle: Bundle, cfg: ScoringConfig) -> None:
    """TS-IND-254: a changed config period changes the values and the config hash."""
    as_of = _date(bundle, N - 1)
    base = compute_snapshot(bundle, cfg, as_of)
    raw = cfg.model_dump(mode="json")
    raw["supertrend"]["factor"] = 2.0
    changed_cfg = parse_scoring_config(raw)
    changed = compute_snapshot(bundle, changed_cfg, as_of)
    assert changed["daily"]["supertrend"]["line"] != base["daily"]["supertrend"]["line"]
    assert changed["config_hash"] == config_hash(changed_cfg) != base["config_hash"]


def test_unit_snapshot_rejects_dates_without_bars(bundle: Bundle, cfg: ScoringConfig) -> None:
    """TS-IND-255: an as-of date before the first bar is an error; a later one uses the last bar."""
    with pytest.raises(ValueError, match="no bars"):
        compute_snapshot(bundle, cfg, date(1999, 1, 1))
    doc = compute_snapshot(bundle.head(300), cfg, date(2100, 1, 1))
    assert doc["bar_date"] == str(bundle.dates[299])
    assert doc["as_of"] == "2100-01-01"
