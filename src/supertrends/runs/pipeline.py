# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Pure steps of the daily run: exclusions, scoring, row building, summary (FR-906, ADR-066).

No I/O, clock, or randomness: the orchestrator loads inputs and writes the rows built here, so
two runs over the same bars and config produce identical rows (NFR-002).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from supertrends.data.quality import Quality, classify_quality
from supertrends.scoring.composite import ScoreCard, score_ticker
from supertrends.scoring.config import ScoringConfig
from supertrends.scoring.factor import Factor, FactorContext, FactorResult
from supertrends.scoring.factor import Quality as FactorQuality
from supertrends.selection import (
    CandidateCheck,
    Exclusion,
    SelectionInput,
    buy_threshold,
    evaluate_candidate,
    rank_key,
    selection_input_from_snapshot,
    sell_threshold,
)
from supertrends.selection.ranking import Selection

__all__ = [
    "EXCLUSION_REASONS",
    "ScoredTicker",
    "build_summary",
    "classify_universe",
    "display_decimal",
    "excluded_row",
    "factor_score_rows",
    "json_safe",
    "rank_overall",
    "score_one",
    "ticker_score_row",
]

STALE = "stale"
INSUFFICIENT_HISTORY = "insufficient_history"
NO_DATA = "no_data"
UNRESOLVED = "unresolved"
EXCLUSION_REASONS = (STALE, INSUFFICIENT_HISTORY, NO_DATA, UNRESOLVED)
_EXCLUDED_QUALITIES = frozenset({STALE, INSUFFICIENT_HISTORY})


def json_safe(value: Any) -> Any:
    """`value` with every non-finite float replaced by None (JSONB has no NaN or Infinity)."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [json_safe(v) for v in value]
    return value


def display_decimal(value: float) -> Decimal:
    """A 0..100 display value as `numeric(4,1)` (ADR-030: one decimal, no float drift)."""
    return Decimal(f"{value:.1f}")


def classify_universe(
    symbols: Iterable[str],
    bar_dates: Mapping[str, Sequence[date]],
    trade_date: date,
    *,
    unresolved: Iterable[str] = (),
) -> tuple[dict[str, Quality], tuple[Exclusion, ...]]:
    """Data quality per symbol and the exclusions, sorted by ticker (FR-107, FR-108, FR-412).

    `bar_dates` holds each symbol's stored daily bar dates on or before `trade_date`. Reasons:
    `unresolved` (the provider does not know the symbol), `no_data` (no bars), then the
    quality classes `insufficient_history` and `stale`. `degraded` tickers are scored.
    """
    gone = set(unresolved)
    quality: dict[str, Quality] = {}
    excluded: list[Exclusion] = []
    for symbol in sorted(set(symbols)):
        dates = bar_dates.get(symbol, ())
        quality[symbol] = classify_quality(dates, trade_date)
        if symbol in gone:
            excluded.append(Exclusion(symbol, UNRESOLVED))
        elif not dates:
            excluded.append(Exclusion(symbol, NO_DATA))
        elif quality[symbol] in _EXCLUDED_QUALITIES:
            excluded.append(Exclusion(symbol, quality[symbol]))
    return quality, tuple(excluded)


@dataclass(frozen=True)
class ScoredTicker:
    """One scored ticker: its snapshot, factor results, score card and candidate verdicts."""

    ticker: str
    quality: Quality
    snapshot: Mapping[str, Any]
    results: Mapping[str, FactorResult]
    card: ScoreCard
    entry: SelectionInput
    check: CandidateCheck


def score_one(
    ticker: str,
    snapshot: Mapping[str, Any],
    factors: Sequence[Factor],
    context: FactorContext,
    quality: Quality,
) -> ScoredTicker:
    """Run the factors, the composite and the candidate rules for one ticker.

    Raises NoScorableFactorsError (every factor missing); the caller excludes the ticker.
    """
    results = {f.id: f.compute(snapshot, context) for f in factors}
    card = score_ticker(snapshot, results, context)
    entry = selection_input_from_snapshot(ticker, card, snapshot, data_quality=quality)
    return ScoredTicker(
        ticker=ticker,
        quality=quality,
        snapshot=snapshot,
        results=results,
        card=card,
        entry=entry,
        check=evaluate_candidate(entry, context.config),
    )


def rank_overall(scored: Sequence[ScoredTicker]) -> dict[str, int]:
    """1-based rank by display descending with the buy-side tie-breakers (`rank_overall`)."""
    ordered = sorted(scored, key=lambda s: rank_key(s.entry, "buy"))
    return {s.ticker: i for i, s in enumerate(ordered, start=1)}


def _candidate(check: CandidateCheck) -> str | None:
    if check.buy.qualified:
        return "buy"
    if check.sell.qualified:
        return "sell"
    return None


def _flags(st: ScoredTicker, config: ScoringConfig) -> list[str]:
    flags = []
    if st.card.event_risk:
        flags.append("event_risk")
    adv = st.entry.avg_dollar_volume_20d
    if adv is None or adv < config.liquidity.min_avg_dollar_volume_20d:
        flags.append("low_liquidity")
    return flags


def _int_or_none(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return None
    return int(value)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _snapshot_value(snapshot: Mapping[str, Any], *keys: str) -> Any:
    node: Any = snapshot
    for key in keys:
        if not isinstance(node, Mapping) or key not in node:
            return None
        node = node[key]
    return node


def ticker_score_row(
    run_id: str, st: ScoredTicker, rank: int, config: ScoringConfig
) -> dict[str, Any]:
    """The `ticker_scores` row of a scored ticker."""
    card = st.card
    detail = card.weight_detail
    return {
        "run_id": run_id,
        "symbol": st.ticker,
        "status": "scored",
        "exclusion_reason": None,
        "data_quality": st.quality,
        "composite": card.composite,
        "display_score": display_decimal(card.display_score),
        "band": str(card.band),
        "confidence": card.confidence,
        "regime": card.regime,
        "st_dir_d": st.entry.st_dir_d,
        "st_dir_w": _int_or_none(_snapshot_value(st.snapshot, "weekly", "supertrend_direction")),
        "bars_since_flip": st.entry.bars_since_flip,
        "st_line": _float_or_none(_snapshot_value(st.snapshot, "daily", "supertrend", "line")),
        "buy_threshold": display_decimal(buy_threshold(st.entry, config)),
        "sell_threshold": display_decimal(sell_threshold(st.entry, config)),
        "candidate": _candidate(st.check),
        "rank_overall": rank,
        "weights": json_safe(
            {fid: {"base": detail.base[fid], "final": card.weights[fid]} for fid in card.weights}
        ),
        "adjustments": list(card.adjustments),
        "flags": _flags(st, config),
        "avg_dollar_volume_20d": st.entry.avg_dollar_volume_20d,
        "rel_volume": st.entry.relative_volume,
    }


def excluded_row(run_id: str, exclusion: Exclusion, quality: Quality) -> dict[str, Any]:
    """The `ticker_scores` row of an excluded ticker (not scored, reason required)."""
    return {
        "run_id": run_id,
        "symbol": exclusion.ticker,
        "status": "excluded",
        "exclusion_reason": exclusion.reason,
        "data_quality": quality,
    }


def factor_score_rows(run_id: str, st: ScoredTicker) -> list[dict[str, Any]]:
    """One `factor_scores` row per factor; a missing factor stores score NULL."""
    rows = []
    for fid, result in st.results.items():
        missing = result.quality == FactorQuality.MISSING
        rows.append(
            {
                "run_id": run_id,
                "symbol": st.ticker,
                "factor_id": fid,
                "score": None if missing else result.score,
                "weight": st.card.weights[fid],
                "contribution": st.card.contributions[fid],
                "quality": str(result.quality),
                "evidence": json_safe(
                    {
                        "items": [e.model_dump(mode="json") for e in result.evidence],
                        "weight_multiplier": result.weight_multiplier,
                    }
                ),
            }
        )
    return rows


def build_summary(  # noqa: PLR0913 - one keyword per summary section
    *,
    trade_date: date,
    config_hash: str,
    scoring_version: int,
    symbols: Sequence[str],
    scored: Sequence[ScoredTicker],
    excluded: Sequence[Exclusion],
    quality: Mapping[str, Quality],
    provider_errors: Mapping[str, Sequence[str]],
    selection: Selection | None,
) -> dict[str, Any]:
    """The deterministic part of `runs.summary` (FR-906). The orchestrator adds durations and
    narrative counts."""
    counts: dict[str, int] = {}
    for status in quality.values():
        counts[status] = counts.get(status, 0) + 1
    summary: dict[str, Any] = {
        "trade_date": trade_date.isoformat(),
        "config_hash": config_hash,
        "scoring_version": scoring_version,
        "tickers_total": len(set(symbols)),
        "tickers_scored": len(scored),
        "tickers_excluded": len(excluded),
        "excluded": [
            {"ticker": e.ticker, "reason": e.reason}
            for e in sorted(excluded, key=lambda e: e.ticker)
        ],
        "quality_counts": dict(sorted(counts.items())),
        "provider_errors": [
            {"ticker": t, "errors": list(errs)} for t, errs in sorted(provider_errors.items())
        ],
    }
    if selection is not None:
        summary["buys"] = [p.ticker for p in selection.buys]
        summary["sells"] = [p.ticker for p in selection.sells]
        summary["also_qualified"] = [
            {
                "ticker": a.ticker,
                "side": a.side,
                "duplicates": a.duplicates,
                "correlation": a.correlation,
            }
            for a in selection.also_qualified
        ]
        summary["nearest_miss"] = {
            side: None
            if miss is None
            else {
                "ticker": miss.ticker,
                "display_score": miss.display_score,
                "threshold": miss.threshold,
                "reason": miss.reason,
            }
            for side, miss in sorted(selection.nearest_miss.items())
        }
    return json_safe(summary)  # type: ignore[no-any-return]
