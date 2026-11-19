# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor framework: result, evidence, context, templates (S3-T01; Signal Engine Conventions)."""

import dataclasses
import math
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from supertrends.scoring.config import ScoringConfig, load_scoring_config
from supertrends.scoring.factor import (
    EvidenceItem,
    FactorContext,
    FactorResult,
    Quality,
    ReasonTemplate,
    format_number,
)

CONFIG = Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"


@pytest.fixture(scope="module")
def cfg() -> ScoringConfig:
    return load_scoring_config(CONFIG)


def _item(**over: Any) -> EvidenceItem:
    base: dict[str, Any] = {
        "name": "st_dir_d",
        "value": 1,
        "unit": "direction",
        "reason": "Daily Supertrend is up",
    }
    return EvidenceItem(**{**base, **over})


def _result(score: float, **over: Any) -> FactorResult:
    base: dict[str, Any] = {
        "factor_id": "supertrend",
        "score": score,
        "quality": Quality.OK,
        "evidence": (_item(),),
    }
    return FactorResult(**{**base, **over})


def test_unit_factor_result_score_101_raises_validation_error() -> None:
    """TS-SCR-001: a factor returning 101 raises."""
    with pytest.raises(ValidationError, match="score"):
        _result(101)


def test_unit_factor_result_score_minus_101_raises_validation_error() -> None:
    """TS-SCR-002: a factor returning -101 raises."""
    with pytest.raises(ValidationError, match="score"):
        _result(-101)


@pytest.mark.parametrize("score", [100, -100, 0, 99.99, -0.0001])
def test_unit_factor_result_score_inside_closed_range_is_accepted(score: float) -> None:
    """TS-SCR-001: the range is closed, so both ends are valid."""
    assert _result(score).score == score


@pytest.mark.parametrize("score", [math.nan, math.inf, -math.inf, 100.0000001])
def test_unit_factor_result_nan_inf_and_just_out_of_range_scores_raise(score: float) -> None:
    """TS-SCR-314: NaN and infinities never become a score; the range check has no slack."""
    with pytest.raises(ValidationError):
        _result(score)


def test_unit_factor_result_contains_evidence_items_name_value_unit_reason_and_quality() -> None:
    """TS-SCR-004: FactorResult carries id, score, quality, evidence (name, value, unit, reason)."""
    res = _result(60, evidence=(_item(), _item(name="line", value=212.4, unit="usd")))
    assert res.factor_id == "supertrend"
    assert res.quality is Quality.OK
    assert [(e.name, e.value, e.unit, e.reason) for e in res.evidence] == [
        ("st_dir_d", 1, "direction", "Daily Supertrend is up"),
        ("line", 212.4, "usd", "Daily Supertrend is up"),
    ]
    assert res.reasons == ("Daily Supertrend is up", "Daily Supertrend is up")
    assert res.weight_multiplier == 1.0


def test_unit_factor_quality_vocabulary_is_ok_degraded_missing_daily_estimate() -> None:
    """TS-SCR-306: the stored vocabulary (ARCHITECTURE factor_scores.quality), as strings."""
    assert [q.value for q in Quality] == ["ok", "degraded", "missing", "daily_estimate"]
    assert Quality("degraded") is Quality.DEGRADED
    assert _result(0, quality="degraded").quality == "degraded"  # plain strings validate
    with pytest.raises(ValidationError):
        _result(0, quality="stale")


def test_unit_factor_result_is_frozen_and_rejects_unknown_fields() -> None:
    """TS-SCR-314: results are immutable records and strict about their shape."""
    res = _result(10)
    with pytest.raises(ValidationError):
        res.score = 20  # type: ignore[misc]
    with pytest.raises(ValidationError):
        _result(10, surprise=1)


@pytest.mark.parametrize("multiplier", [0.0, -0.5, math.nan, math.inf])
def test_unit_factor_result_weight_multiplier_must_be_positive_and_finite(
    multiplier: float,
) -> None:
    """TS-SCR-314: the weight multiplier carrier (0.6 flow estimate, 0.5 stale) is > 0."""
    with pytest.raises(ValidationError):
        _result(0, weight_multiplier=multiplier)


def test_unit_factor_result_weight_multiplier_carries_quality_discount() -> None:
    """TS-SCR-314: Factor 10 daily_estimate (x0.6) and Factor 11 stale (x0.5) ride on the result."""
    flow = _result(10, factor_id="flow", quality=Quality.DAILY_ESTIMATE, weight_multiplier=0.6)
    assert flow.weight_multiplier == 0.6
    assert flow.quality is Quality.DAILY_ESTIMATE


def test_unit_factor_result_missing_helper_scores_zero_with_missing_quality() -> None:
    """TS-SCR-309: `missing` is score 0, quality missing, one explanatory evidence item."""
    res = FactorResult.missing("fundamentals", reason="No fundamentals for this ticker")
    assert (res.score, res.quality, res.weight_multiplier) == (0.0, Quality.MISSING, 1.0)
    assert res.is_missing
    assert [e.reason for e in res.evidence] == ["No fundamentals for this ticker"]
    assert not _result(5).is_missing


def test_unit_factor_result_missing_with_nonzero_score_is_rejected() -> None:
    """TS-SCR-309: a missing factor is excluded from the composite, so its score must be 0."""
    with pytest.raises(ValidationError, match="missing"):
        _result(5, quality=Quality.MISSING)


@pytest.mark.parametrize(
    "bad",
    [
        {"name": ""},
        {"unit": ""},
        {"reason": ""},
        {"value": math.nan},
        {"value": math.inf},
        {"value": [1, 2]},
    ],
)
def test_unit_evidence_item_rejects_empty_text_non_finite_numbers_and_containers(
    bad: dict[str, Any],
) -> None:
    """TS-SCR-004: evidence items are scalar, finite and fully described."""
    with pytest.raises(ValidationError):
        _item(**bad)


@pytest.mark.parametrize("value", [1, 2.5, "up", True, None])
def test_unit_evidence_item_accepts_scalar_values_and_keeps_their_type(value: Any) -> None:
    """TS-SCR-004: int stays int, bool stays bool, None means not available (never 0)."""
    got = _item(value=value).value
    assert got == value
    assert type(got) is type(value)


def test_unit_factor_context_defaults_and_immutability(cfg: ScoringConfig) -> None:
    """TS-SCR-316: the context is config + as_of with injectable regime, fundamentals, events."""
    ctx = FactorContext(config=cfg, as_of=date(2026, 11, 13))
    assert ctx.regime is None
    assert ctx.fundamentals is None
    assert ctx.days_to_earnings is None
    assert ctx.event_risk is False
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.regime = "trending"  # type: ignore[misc]
    full = FactorContext(
        config=cfg,
        as_of=date(2026, 11, 13),
        regime="trending",
        fundamentals={"revenue_growth_yoy": 0.12},
        days_to_earnings=3,
        event_risk=True,
    )
    assert (full.regime, full.days_to_earnings, full.event_risk) == ("trending", 3, True)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        # hand-derived: ints print as is; floats are fixed to 2 decimals (negative zero prints
        # as 0.00); negatives keep the sign.
        (3, "3"),
        (-12, "-12"),
        (212.4, "212.40"),
        (1.2, "1.20"),
        (0.0, "0.00"),
        (-0.004, "0.00"),
        (1234567.891, "1234567.89"),
        (True, "true"),
        (False, "false"),
        ("up", "up"),
    ],
)
def test_unit_reason_number_formatting_is_consistent(value: Any, text: str) -> None:
    """TS-SCR-315: numbers in reasons use one format, so the narrative can match evidence."""
    assert format_number(value) == text


def test_unit_reason_number_formatting_rejects_non_finite() -> None:
    """TS-SCR-315: NaN never reaches a reason string."""
    with pytest.raises(ValueError, match="finite"):
        format_number(math.nan)


def test_unit_reason_template_renders_named_placeholders_deterministically() -> None:
    """TS-SCR-006: one template per rule that fired; same inputs give the same string."""
    t = ReasonTemplate("st_fresh_flip", "Daily Supertrend flipped {direction} {bars} bars ago")
    assert t.render(direction="up", bars=3) == "Daily Supertrend flipped up 3 bars ago"
    assert t.render(bars=3, direction="up") == t.render(direction="up", bars=3)
    assert t.placeholders == ("direction", "bars")


def test_unit_reason_template_formats_floats_with_the_shared_formatter() -> None:
    """TS-SCR-315: a float placeholder is rendered by `format_number`."""
    t = ReasonTemplate("st_stretch", "Close is {atr} ATR from the line at {line}")
    assert t.render(atr=4.256, line=212.4) == "Close is 4.26 ATR from the line at 212.40"


def test_unit_reason_template_rejects_missing_extra_and_positional_placeholders() -> None:
    """TS-SCR-006: a template must be rendered with exactly its named values."""
    t = ReasonTemplate("x", "A {a} and {b}")
    with pytest.raises(KeyError, match="b"):
        t.render(a=1)
    with pytest.raises(KeyError, match="c"):
        t.render(a=1, b=2, c=3)
    for bad in ("A {} b", "A {0} b", "A {a.real} b", "A {a!r} b", "A {a:>5} b"):
        with pytest.raises(ValueError, match="named"):
            ReasonTemplate("bad", bad)


def test_unit_reason_template_requires_an_id_and_literal_braces_are_escaped() -> None:
    """TS-SCR-006: ids are non-empty; doubled braces stay literal."""
    with pytest.raises(ValueError, match="id"):
        ReasonTemplate("", "text")
    assert ReasonTemplate("lit", "{{a}} is {a}").render(a=1) == "{a} is 1"


def test_unit_reason_template_evidence_builds_an_item_whose_reason_is_the_rendering() -> None:
    """TS-SCR-006: `evidence` makes the item from the template, value and unit."""
    t = ReasonTemplate("st_dist", "Close is {value} ATR above the Supertrend line")
    item = t.evidence("st_distance_atr", 1.2, "atr", value=1.2)
    assert (item.name, item.value, item.unit) == ("st_distance_atr", 1.2, "atr")
    assert item.reason == "Close is 1.20 ATR above the Supertrend line"
