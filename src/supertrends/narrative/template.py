# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""The deterministic template narrative (BUILD_PROMPT "Justification"; FR-5xx; ADR-067; S3-T08).

Three to five sentences, built only from the evidence document, in the spec order:

1. the Supertrend state and the 34/50 cloud bias (with the score, band and confidence),
2. the two largest contributions in the side's direction,
3. the largest opposing factor ("what argues against it"), omitted when none argues against,
4. the invalidation level and rule,
5. the nearest level on the way (`levels.next_target`), omitted when there is none.

A sell is a bearish label only: the text never mentions shorting, sizing, options or leverage.
Every number is formatted from the evidence value (1 decimal for points, 2 for prices), so the
numeric guard accepts it. `narrate` is pure and returns the same result for the same document.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from supertrends.narrative.guard import extract_numbers

__all__ = ["FACTOR_LABELS", "NarrativeResult", "count_sentences", "narrate"]

FACTOR_LABELS: Mapping[str, str] = {
    "supertrend": "the Supertrend",
    "sma": "the moving averages",
    "macd": "MACD",
    "divergence": "divergence",
    "mean_reversion": "mean reversion",
    "fibonacci": "the Fibonacci levels",
    "levels": "support and resistance",
    "volatility": "volatility",
    "volume_osc": "the volume oscillator",
    "flow": "order flow",
    "fundamentals": "fundamentals",
    "ripster": "the Ripster EMA clouds",
}
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_DIRECTION = {1: "bullish", -1: "bearish"}
_CLOUD_BIAS = {1: "above", 0: "inside", -1: "below"}


@dataclass(frozen=True)
class NarrativeResult:
    """A narrative: its text, where it came from, and what it contains.

    `source` is `template` here; Sprint 5 adds `llm` with the model name and prompt version.
    `numbers` are the numbers found in the text; `sentences` is the sentence count.
    """

    text: str
    source: str
    numbers: tuple[float, ...]
    sentences: int
    model: str | None = None
    prompt_version: str | None = None


def count_sentences(text: str) -> int:
    """Sentences in `text` (a full stop inside a number such as 78.4 does not end one)."""
    return len([part for part in _SENTENCE_END.split(text.strip()) if part])


def _lead(doc: Mapping[str, Any]) -> str:
    st = doc["supertrend"]
    state = _DIRECTION.get(st["dir_d"])
    if state is None:
        supertrend = "the daily Supertrend state is not available"
    else:
        bars = st["bars_since_flip"]
        flip = "" if bars is None else f" (flipped {bars} {'bar' if bars == 1 else 'bars'} ago)"
        supertrend = f"the daily Supertrend is {state}{flip}"
    bias = doc["ripster"]["bias"]
    cloud = doc["cloud_label"]
    if bias in _CLOUD_BIAS:
        cloud_text = f"the close is {_CLOUD_BIAS[bias]} the {cloud} EMA cloud"
    else:
        cloud_text = f"the close against the {cloud} EMA cloud is not available"
    label = "bullish" if doc["side"] == "buy" else "bearish"
    return (
        f"{doc['ticker']} is a {label} pick: {supertrend} and {cloud_text}, "
        f"with a display score of {doc['display_score']:.1f} ({doc['band']}) "
        f"and confidence {doc['confidence']:.1f}."
    )


def _points(factor: Mapping[str, Any]) -> str:
    return f"{FACTOR_LABELS[factor['id']]} ({factor['contribution']:+.1f} points)"


def narrate(evidence: Mapping[str, Any]) -> NarrativeResult:
    """The template narrative of one evidence document (pure; no I/O)."""
    direction = 1 if evidence["side"] == "buy" else -1
    scored = sorted(
        (f for f in evidence["factors"] if f["weight"] > 0),
        key=lambda f: -direction * f["contribution"],
    )
    supporting = [f for f in scored if direction * f["contribution"] > 0][:2]
    sentences = [_lead(evidence)]
    if len(supporting) == 2:
        sentences.append(
            f"The largest contributions in this direction are {_points(supporting[0])} "
            f"and {_points(supporting[1])}."
        )
    elif supporting:
        sentences.append(f"The only contribution in this direction is {_points(supporting[0])}.")
    else:
        sentences.append("No factor contributes in this direction.")
    if scored and direction * scored[-1]["contribution"] < 0:
        sentences.append(f"What argues against it is {_points(scored[-1])}.")
    inv = evidence["invalidation"]
    if inv["level"] is None:
        sentences.append(
            "No invalidation level is available because the Supertrend line is not defined."
        )
    else:
        sentences.append(f"The view is wrong on a {inv['rule']} at {inv['level']:.2f}.")
    target = evidence["levels"]["next_target"]
    if target is not None:
        sentences.append(f"The nearest level on the way is {target:.2f}.")
    text = " ".join(sentences)
    return NarrativeResult(
        text=text,
        source="template",
        numbers=tuple(extract_numbers(text)),
        sentences=count_sentences(text),
    )
