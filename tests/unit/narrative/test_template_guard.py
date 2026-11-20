# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Template narrative and numeric guard (TS-NAR-006 to 009, 106 to 112; S3-T08; ADR-067)."""

from __future__ import annotations

import copy
import re
from typing import Any

import pytest

from supertrends.narrative.evidence import build_evidence
from supertrends.narrative.guard import check_numbers, evidence_numbers, extract_numbers
from supertrends.narrative.template import count_sentences, narrate
from tests.unit.narrative.nar_support import Scored, cfg, many


def _doc(s: Scored) -> dict[str, Any]:
    return build_evidence(
        s.pick, snapshot=s.snapshot, results=s.results, config=cfg(), trade_date=s.as_of
    )


def _sentences(text: str) -> list[str]:
    return [p for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p]


def test_unit_narrative_template_leads_with_supertrend_and_34_50_cloud_bias_then_top_two_then_opposing_then_invalidation() -> (  # noqa: E501
    None
):
    """TS-NAR-006."""
    checked = False
    for s in many():
        doc = _doc(s)
        text = narrate(doc).text
        side = 1 if doc["side"] == "buy" else -1
        ranked = sorted(
            (f for f in doc["factors"] if f["weight"] > 0),
            key=lambda f: -side * f["contribution"],
        )
        top = [f for f in ranked if side * f["contribution"] > 0][:2]
        first = _sentences(text)[0]
        assert "Supertrend" in first
        assert "34/50" in first
        # positions of the ordered parts
        pos = [text.index("Supertrend")]
        for f in top:
            pos.append(text.index(f"{f['contribution']:+.1f}"))
        against = ranked[-1]
        if side * against["contribution"] < 0:
            pos.append(text.index(f"{against['contribution']:+.1f}"))
            checked = True
        inv = doc["invalidation"]["level"]
        if inv is not None:
            pos.append(text.index(f"{inv:.2f}"))
        assert pos == sorted(pos), text
    assert checked


def test_unit_narrative_template_every_number_appears_in_evidence_document() -> None:
    """TS-NAR-007: over 6 series x 4 dates x both sides."""
    for s in many():
        doc = _doc(s)
        result = narrate(doc)
        verdict = check_numbers(result.text, doc)
        assert verdict.ok, (verdict.unmatched, result.text)
        assert result.source == "template"


def test_unit_narrative_template_three_to_five_sentences() -> None:
    """TS-NAR-008."""
    for s in many():
        n = count_sentences(narrate(_doc(s)).text)
        assert 3 <= n <= 5


def test_unit_narrative_template_no_opposing_factor_omits_line_without_inventing() -> None:
    """TS-NAR-009."""
    s = Scored(1, 380, "buy")
    doc = _doc(s)
    for f in doc["factors"]:
        if f["weight"] > 0:
            f["contribution"] = abs(f["contribution"])
    text = narrate(doc).text
    assert "against" not in text.lower()
    assert 3 <= count_sentences(text) <= 5
    assert check_numbers(text, doc).ok


def test_unit_narrative_template_sell_is_bearish_label_without_trade_advice() -> None:
    """TS-NAR-106."""
    for s in many(range(1, 4)):
        doc = _doc(s)
        text = narrate(doc).text.lower()
        words = set(re.findall(r"[a-z']+", text))
        assert not words & {"short", "shorting", "position", "options", "leverage", "will"}
        assert "guaranteed" not in text
        if doc["side"] == "sell":
            assert "bearish" in text
        else:
            assert "bullish" in text


def test_unit_narrative_template_is_deterministic_and_reports_numbers() -> None:
    """TS-NAR-107."""
    s = Scored(3, 380, "buy")
    doc = _doc(s)
    a, b = narrate(doc), narrate(copy.deepcopy(doc))
    assert a == b
    assert a.numbers == tuple(extract_numbers(a.text))
    assert a.sentences == count_sentences(a.text)


def test_unit_narrative_template_handles_missing_line_and_unknown_cloud_bias() -> None:
    """TS-NAR-108: null invalidation, bias, direction and target never print None or a number."""
    s = Scored(1, 380, "sell")
    doc = _doc(s)
    doc["invalidation"]["level"] = None
    doc["ripster"]["bias"] = None
    doc["supertrend"]["dir_d"] = None
    doc["supertrend"]["bars_since_flip"] = None
    doc["supertrend"]["distance_atr"] = None
    doc["levels"]["next_target"] = None
    text = narrate(doc).text
    assert "None" not in text
    assert "nan" not in text.lower()
    assert 3 <= count_sentences(text) <= 5
    assert check_numbers(text, doc).ok


def test_unit_numeric_guard_number_not_in_evidence_rejects() -> None:
    """TS-NAR-109 (S5-T02 hardens this path)."""
    doc = _doc(Scored(1, 380, "buy"))
    verdict = check_numbers("The stock is at 987654.32 today.", doc)
    assert not verdict.ok
    assert verdict.unmatched == (987654.32,)


def test_unit_numeric_guard_number_matching_within_rounding_accepts() -> None:
    """TS-NAR-110."""
    doc = _doc(Scored(1, 380, "buy"))
    level = doc["invalidation"]["level"]
    assert check_numbers(f"Close below {level:.1f}, or {level:.0f}.", doc).ok
    assert not check_numbers(f"Close below {level + 0.5:.2f}.", doc).ok


def test_unit_numeric_guard_percent_and_decimal_formats_extracted() -> None:
    """TS-NAR-111."""
    assert extract_numbers("up 3.2%, 1,234.5 and -4 or +7.25 in 34/50") == [
        3.2,
        1234.5,
        -4.0,
        7.25,
        34.0,
        50.0,
    ]
    assert extract_numbers("no digits here.") == []


def test_unit_numeric_guard_collects_numbers_from_values_and_reason_strings() -> None:
    """TS-NAR-112."""
    doc = _doc(Scored(1, 380, "buy"))
    pool = evidence_numbers(doc)
    assert doc["confidence"] in pool or round(doc["confidence"], 1) in pool
    assert {34.0, 50.0} <= pool
    assert all(isinstance(v, float) for v in pool)
    with pytest.raises(TypeError):
        evidence_numbers("not a document")  # type: ignore[arg-type]
