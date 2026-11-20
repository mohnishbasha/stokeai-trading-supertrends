# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Evidence document (TS-NAR-001 to 005, 039, 101 to 106; S3-T08; ADR-067)."""

from __future__ import annotations

import copy
import json
import math

import jsonschema
import pytest

from supertrends.narrative.evidence import RULE_BUY, RULE_SELL, build_evidence
from supertrends.scoring.config import FACTOR_IDS, config_hash
from supertrends.scoring.ripster_rules import ripster_evidence
from tests.unit.narrative.nar_support import Scored, cfg, many, schema


def _build(s: Scored, **over: object) -> dict[str, object]:
    return build_evidence(
        s.pick, snapshot=s.snapshot, results=s.results, config=cfg(), trade_date=s.as_of, **over
    )  # type: ignore[arg-type]


def test_unit_evidence_build_document_validates_against_committed_json_schema() -> None:
    """TS-NAR-001."""
    jsonschema.Draft202012Validator.check_schema(schema())
    for s in many():
        jsonschema.validate(_build(s), schema())


def test_unit_evidence_build_contributions_sum_to_composite() -> None:
    """TS-NAR-002."""
    for s in many(range(1, 4)):
        doc = _build(s)
        factors = doc["factors"]
        assert [f["id"] for f in factors] == list(FACTOR_IDS)  # type: ignore[index,union-attr]
        total = math.fsum(f["contribution"] for f in factors)  # type: ignore[union-attr,misc]
        assert total == pytest.approx(s.card.composite, abs=1e-3)
        assert doc["composite"] == pytest.approx(s.card.composite, abs=1e-4)
        for f in factors:  # type: ignore[union-attr]
            assert f["contribution"] == pytest.approx(f["weight"] * f["score"] / 100, abs=1e-3)


def test_unit_evidence_build_includes_invalidation_level_and_rule() -> None:
    """TS-NAR-003."""
    for s in many(range(1, 4)):
        doc = _build(s)
        line = s.snapshot["daily"]["supertrend"]["line"]
        assert doc["invalidation"]["level"] == pytest.approx(line, abs=1e-4)  # type: ignore[index]
        want = RULE_BUY if s.pick.side == "buy" else RULE_SELL
        assert doc["invalidation"]["rule"] == want  # type: ignore[index]
    assert RULE_BUY == "daily close below the Supertrend line"
    assert RULE_SELL == "daily close above the Supertrend line"


def test_unit_evidence_build_includes_levels_support_resistance_fib_next_target() -> None:
    """TS-NAR-004."""
    seen_target = False
    for s in many():
        doc = _build(s)
        lv = doc["levels"]
        close = s.snapshot["daily"]["close"]
        assert all(p < close for p in lv["support"])  # type: ignore[index,union-attr]
        assert all(p > close for p in lv["resistance"])  # type: ignore[index,union-attr]
        assert lv["support"] == sorted(lv["support"], reverse=True)  # type: ignore[index]
        assert lv["resistance"] == sorted(lv["resistance"])  # type: ignore[index]
        for key, price in lv["fib"].items():  # type: ignore[index,union-attr]
            assert float(key) > 0
            assert isinstance(price, float)
        target = lv["next_target"]  # type: ignore[index]
        if target is not None:
            seen_target = True
            assert (target > close) == (s.pick.side == "buy")
    assert seen_target


def test_unit_evidence_build_includes_adjustments_flags_and_config_hash() -> None:
    """TS-NAR-005."""
    s = Scored(1, 380, "buy")
    doc = _build(s)
    assert doc["config_hash"] == config_hash(cfg())
    assert doc["config_version"] == cfg().scoring.version
    assert doc["adjustments"] == list(s.card.adjustments)
    assert doc["flags"] == sorted(doc["flags"])  # type: ignore[type-var]
    assert doc["ticker"] == s.pick.ticker
    assert doc["date"] == s.as_of.isoformat()
    assert doc["side"] == s.pick.side
    assert doc["band"] == s.card.band.value
    assert doc["rank"] == 1
    assert doc["days_on_list"] == 2


def test_unit_evidence_build_includes_ripster_block_and_levels_cloud_34_50() -> None:
    """TS-NAR-039."""
    for s in many(range(1, 4)):
        doc = _build(s)
        assert doc["ripster"] == ripster_evidence(s.snapshot)
        bot, top = s.snapshot["ripster"]["c3_bot"], s.snapshot["ripster"]["c3_top"]
        cloud = doc["levels"]["cloud_34_50"]  # type: ignore[index]
        assert cloud == [pytest.approx(bot, abs=1e-4), pytest.approx(top, abs=1e-4)]
        assert doc["cloud_label"] == "34/50"
        jsonschema.validate(doc, schema())


def test_unit_evidence_build_is_json_serializable_pure_and_deterministic() -> None:
    """TS-NAR-101."""
    s = Scored(2, 380, "sell")
    snap = copy.deepcopy(s.snapshot)
    a, b = _build(s), _build(s)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert s.snapshot == snap
    json.dumps(a, allow_nan=False)


def test_unit_evidence_build_flags_event_risk_degraded_and_estimated_flow() -> None:
    """TS-NAR-102."""
    flags: set[str] = set()
    for s in many():
        flags.update(_build(s)["flags"])  # type: ignore[arg-type]
    assert flags <= {"event_risk", "degraded_data", "estimated_order_flow", "data_stale"}
    s = Scored(1, 380, "buy")
    entry = s.pick.entry
    import dataclasses

    stale = dataclasses.replace(s.pick, entry=dataclasses.replace(entry, data_quality="stale"))
    doc = build_evidence(
        stale,
        snapshot=s.snapshot,
        results=s.results,
        config=cfg(),
        trade_date=s.as_of,
    )
    assert "data_stale" in doc["flags"]
    jsonschema.validate(doc, schema())


def test_unit_evidence_build_embeds_duplicates_from_also_qualified() -> None:
    """TS-NAR-103."""
    import dataclasses

    from supertrends.selection.ranking import AlsoQualified, Selection

    s = Scored(1, 380, "buy")
    other = Scored(2, 380, "buy")
    aq = AlsoQualified(
        ticker="DUP",
        side="buy",
        display_score=70.0,
        confidence=60.0,
        duplicates=s.pick.ticker,
        correlation=0.93,
        entry=other.pick.entry,
    )
    unrelated = dataclasses.replace(aq, ticker="OTHER", duplicates="ZZZ")
    sel = Selection(
        buys=(s.pick,),
        sells=(),
        also_qualified=(aq, unrelated),
        nearest_miss={"buy": None, "sell": None},
        excluded=(),
        checks=(),
    )
    doc = _build(s, selection=sel, market_regime="risk_on")
    assert [d["ticker"] for d in doc["also_qualified"]] == ["DUP"]  # type: ignore[union-attr]
    assert doc["also_qualified"][0]["correlation"] == 0.93  # type: ignore[index]
    assert doc["market_regime"] == "risk_on"
    jsonschema.validate(doc, schema())


def test_unit_evidence_schema_rejects_missing_and_unknown_fields() -> None:
    """TS-NAR-104."""
    doc = _build(Scored(1, 380, "buy"))
    for key in ("ticker", "invalidation", "ripster", "config_hash"):
        bad = {k: v for k, v in doc.items() if k != key}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**doc, "extra": 1}, schema())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**doc, "side": "hold"}, schema())


def test_unit_evidence_build_rejects_results_that_do_not_match_the_card() -> None:
    """TS-NAR-105."""
    s = Scored(1, 380, "buy")
    short = {k: v for k, v in s.results.items() if k != "macd"}
    with pytest.raises(ValueError, match="macd"):
        build_evidence(
            s.pick, snapshot=s.snapshot, results=short, config=cfg(), trade_date=s.as_of
        )
