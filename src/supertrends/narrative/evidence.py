# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""The per-pick evidence document (BUILD_PROMPT "Justification"; FR-5xx; ADR-067; S3-T08).

`build_evidence` turns one pick's scoring outputs into a plain JSON-able dict that validates
against `schemas/evidence.schema.json`: the score card (score, band, confidence, deductions,
weights, contributions, adjustments), each factor's reasons, the Supertrend and Ripster blocks, the
invalidation level and rule, support, resistance, Fibonacci levels and the next level, flags, and
the config hash. Floats are rounded (prices and contributions to 4 decimals, display and
confidence to 1) so the stored document is stable; `contribution = weight * score / 100`.

Pure: no I/O, clock or randomness, and the arguments are never mutated.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from importlib import resources
from typing import Any

from supertrends.scoring.config import FACTOR_IDS, ScoringConfig, config_hash
from supertrends.scoring.factor import FactorResult, Quality
from supertrends.scoring.ripster_rules import ripster_evidence
from supertrends.selection.ranking import Pick, Selection

__all__ = [
    "CLOUD_LABEL",
    "EVIDENCE_SCHEMA_VERSION",
    "RULE_BUY",
    "RULE_SELL",
    "build_evidence",
    "evidence_schema",
]

EVIDENCE_SCHEMA_VERSION = 1
CLOUD_LABEL = "34/50"
RULE_BUY = "daily close below the Supertrend line"
RULE_SELL = "daily close above the Supertrend line"
LEVELS_PER_SIDE = 3
PRICE_DECIMALS = 4


def evidence_schema() -> dict[str, Any]:
    """The committed JSON Schema of the evidence document (package data)."""
    text = (
        resources.files("supertrends.narrative")
        .joinpath("schemas", "evidence.schema.json")
        .read_text(encoding="utf-8")
    )
    loaded: dict[str, Any] = json.loads(text)
    return loaded


def _r(value: float | int | None, digits: int = PRICE_DECIMALS) -> float | None:
    return None if value is None else round(float(value), digits)


def _i(value: float | int | None) -> int | None:
    return None if value is None else int(value)


def _sub(node: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(node, Mapping):
            return None
        node = node.get(key)
    return node


def _prices(entries: Any) -> list[float]:
    if not isinstance(entries, list):
        return []
    return [float(e["price"]) for e in entries]


def _fib(snapshot: Mapping[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for group in ("retracements", "extensions"):
        for item in _sub(snapshot, "fib", group) or []:
            key = f"{float(item['ratio']) * 100:.1f}".removesuffix(".0")
            out[key] = round(float(item["price"]), PRICE_DECIMALS)
    return out


def _next_target(
    side: str, close: float | None, support: list[float], resistance: list[float], fib: list[float]
) -> float | None:
    """The nearest level on the way: a buy looks up (resistance, then a Fibonacci extension above
    the close), a sell looks down (support, then an extension below). None when there is none."""
    if close is None:
        return None
    if side == "buy":
        above = resistance or sorted(p for p in fib if p > close)
        return min(above) if above else None
    below = support or sorted((p for p in fib if p < close), reverse=True)
    return max(below) if below else None


def _flags(pick: Pick) -> list[str]:
    card = pick.entry.card
    flags: set[str] = set()
    if card.event_risk:
        flags.add("event_risk")
    if any(q is Quality.DEGRADED for q in card.qualities.values()):
        flags.add("degraded_data")
    if card.qualities.get("flow") is Quality.DAILY_ESTIMATE:
        flags.add("estimated_order_flow")
    if pick.entry.data_quality != "ok":
        flags.add(f"data_{pick.entry.data_quality}")
    return sorted(flags)


def build_evidence(  # noqa: PLR0913 - one pick's inputs, all keyword-only
    pick: Pick,
    *,
    snapshot: Mapping[str, Any],
    results: Mapping[str, FactorResult],
    config: ScoringConfig,
    trade_date: date,
    selection: Selection | None = None,
    market_regime: str | None = None,
) -> dict[str, Any]:
    """The evidence document of one pick.

    * `pick`: the selected pick (its score card is `pick.entry.card`).
    * `snapshot`: the ticker's indicator snapshot (`scoring.snapshot.compute_snapshot`).
    * `results`: one `FactorResult` per factor (their reasons are listed per factor).
    * `selection`: when given, candidates the correlation guard skipped in favour of this pick are
      listed as `also_qualified`.
    * `market_regime`: injected by the caller (Sprint 5); None until then.

    Raises ValueError when `results` does not cover exactly the twelve factors.
    """
    missing = [fid for fid in FACTOR_IDS if fid not in results]
    unknown = sorted(set(results) - set(FACTOR_IDS))
    if missing or unknown:
        msg = f"results must cover exactly the factor ids; absent {missing}, unknown {unknown}"
        raise ValueError(msg)
    card = pick.entry.card
    close = _sub(snapshot, "daily", "close")
    st = _sub(snapshot, "daily", "supertrend") or {}
    line = _r(st.get("line"))
    sr = _sub(snapshot, "levels", "support_resistance") or {}
    support = sorted(
        (p for p in _prices(sr.get("supports")) if close is not None and p < close), reverse=True
    )
    resistance = sorted(
        p for p in _prices(sr.get("resistances")) if close is not None and p > close
    )
    fib = _fib(snapshot)
    target = _next_target(pick.side, close, support, resistance, list(fib.values()))
    ripster = ripster_evidence(snapshot)
    cloud = [ripster["c3_bot"], ripster["c3_top"]]
    factors = [
        {
            "id": fid,
            "score": _r(card.scores[fid]),
            "weight": _r(card.weights[fid]),
            "contribution": _r(card.contributions[fid]),
            "quality": results[fid].quality.value,
            "reasons": list(results[fid].reasons),
        }
        for fid in FACTOR_IDS
    ]
    duplicates = (
        [
            {
                "ticker": a.ticker,
                "display_score": _r(a.display_score, 1),
                "correlation": _r(a.correlation, 4),
            }
            for a in selection.also_qualified
            if a.duplicates == pick.ticker and a.side == pick.side
        ]
        if selection is not None
        else []
    )
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "ticker": pick.ticker,
        "date": trade_date.isoformat(),
        "side": pick.side,
        "rank": pick.rank,
        "days_on_list": pick.days_on_list,
        "display_score": _r(card.display_score, 1),
        "composite": _r(card.composite),
        "confidence": _r(card.confidence, 1),
        "band": card.band.value,
        "regime": card.regime,
        "market_regime": market_regime,
        "supertrend": {
            "dir_d": _i(st.get("direction")),
            "dir_w": _i(_sub(snapshot, "weekly", "supertrend_direction")),
            "bars_since_flip": _i(_sub(snapshot, "daily", "bars_since_flip")),
            "line": line,
            "distance_atr": _r(_sub(snapshot, "daily", "distance_atr"), 2),
        },
        "ripster": ripster,
        "cloud_label": CLOUD_LABEL,
        "invalidation": {
            "level": line,
            "rule": RULE_BUY if pick.side == "buy" else RULE_SELL,
        },
        "levels": {
            "support": [round(p, PRICE_DECIMALS) for p in support[:LEVELS_PER_SIDE]],
            "resistance": [round(p, PRICE_DECIMALS) for p in resistance[:LEVELS_PER_SIDE]],
            "fib": fib,
            "cloud_34_50": cloud,
            "next_target": _r(target),
        },
        "factors": factors,
        "confidence_deductions": [
            {"code": d.code, "points": _r(d.points, 1), "reason": d.reason} for d in card.deductions
        ],
        "adjustments": list(card.adjustments),
        "flags": _flags(pick),
        "also_qualified": duplicates,
        "config_hash": config_hash(config),
        "config_version": config.scoring.version,
    }
