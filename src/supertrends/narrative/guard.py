# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""The numeric guard (BUILD_PROMPT "Numeric guard"; TEST_PLAN section 8; ADR-067; S3-T08).

Every number in a narrative must match a number in the evidence document within rounding, or the
narrative is rejected. The template path passes by construction and is tested against it; the LLM
path (Sprint 5) reuses it, and S5-T02 adds the banned-phrase and length checks.

Rules (PRD A-35): numbers are digit groups with an optional sign, thousands commas and decimals
(`3.2%`, `1,234.5`, `-4`); a narrative number with d decimals matches an evidence number v when
`|v - n| <= 0.5 * 10**-d` (rounding), comparing absolute values, so a sign is a formatting choice.
The evidence pool is every numeric leaf of the document (booleans excluded) plus every number
inside its string leaves (reasons, the `34/50` label); dates in strings contribute their parts.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = ["GuardResult", "check_numbers", "evidence_numbers", "extract_numbers"]

_NUMBER = re.compile(r"(?<![\d.])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_EPS = 1e-9


@dataclass(frozen=True)
class GuardResult:
    """`ok` is True when every narrative number matched; `unmatched` lists the ones that did not."""

    ok: bool
    unmatched: tuple[float, ...]


def _tokens(text: str) -> list[tuple[float, int]]:
    out: list[tuple[float, int]] = []
    for match in _NUMBER.finditer(text):
        token = match.group(0).replace(",", "")
        decimals = len(token.split(".")[1]) if "." in token else 0
        out.append((float(token), decimals))
    return out


def extract_numbers(text: str) -> list[float]:
    """Every number in `text`, in order, as floats (sign kept, commas and % dropped)."""
    return [value for value, _ in _tokens(text)]


def evidence_numbers(evidence: Mapping[str, Any]) -> frozenset[float]:
    """The absolute value of every number in the evidence document (leaves and string contents)."""
    if not isinstance(evidence, Mapping):
        msg = "evidence must be a mapping"
        raise TypeError(msg)
    pool: set[float] = set()

    def walk(node: Any) -> None:
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, int | float):
            pool.add(abs(float(node)))
        elif isinstance(node, str):
            pool.update(abs(v) for v in extract_numbers(node))
        elif isinstance(node, Mapping):
            for key, value in node.items():
                walk(str(key))
                walk(value)
        elif isinstance(node, Sequence):
            for item in node:
                walk(item)

    walk(evidence)
    return frozenset(pool)


def check_numbers(text: str, evidence: Mapping[str, Any]) -> GuardResult:
    """Check every number of `text` against the evidence document."""
    pool = evidence_numbers(evidence)
    unmatched = tuple(
        value
        for value, decimals in _tokens(text)
        if not any(abs(abs(value) - v) <= 0.5 * 10.0**-decimals + _EPS for v in pool)
    )
    return GuardResult(ok=not unmatched, unmatched=unmatched)
