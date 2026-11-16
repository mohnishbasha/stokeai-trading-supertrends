# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Spec identifiers are unique (TS-IND-244 to TS-IND-246; GATE_DEBT GD-009).

Parallel tasks once reused scenario IDs; this fails the build when a `TS-...` ID appears twice in
the ID column of a TEST_PLAN table, a PRD section 17 `A-nn` appears twice, or an ADR heading
number is repeated in ARCHITECTURE.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[2] / "docs"


def _duplicates(values: list[str]) -> list[str]:
    return sorted(v for v, count in Counter(values).items() if count > 1)


def _first_cells(text: str, pattern: str) -> list[str]:
    ids: list[str] = []
    for line in text.splitlines():
        if line.startswith("|"):
            cell = line.split("|")[1].strip().strip("`")
            if re.fullmatch(pattern, cell):
                ids.append(cell)
    return ids


def test_unit_spec_test_plan_scenario_ids_are_unique() -> None:
    """TS-IND-244: no `TS-...` scenario ID appears twice in the ID column of TEST_PLAN tables."""
    ids = _first_cells((DOCS / "TEST_PLAN.md").read_text(encoding="utf-8"), r"TS-[A-Z]+-\d+")
    assert len(ids) > 300
    assert _duplicates(ids) == []


def test_unit_spec_prd_ambiguity_ids_are_unique() -> None:
    """TS-IND-245: PRD section 17 `A-nn` identifiers are unique."""
    text = (DOCS / "PRD.md").read_text(encoding="utf-8")
    section = text.split("## 17. Ambiguities and resolutions", 1)[1].split("\n## ", 1)[0]
    ids = _first_cells(section, r"A-\d+")
    assert len(ids) >= 20
    assert _duplicates(ids) == []


def test_unit_spec_architecture_adr_headings_are_unique() -> None:
    """TS-IND-246: ADR heading numbers in ARCHITECTURE.md are unique."""
    text = (DOCS / "ARCHITECTURE.md").read_text(encoding="utf-8")
    ids = re.findall(r"^### (ADR-\d+)\b", text, flags=re.MULTILINE)
    assert len(ids) >= 50
    assert _duplicates(ids) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [("| TS-X-001 | a |\n| TS-X-001 | b |\n| TS-X-002 | c |", ["TS-X-001"]), ("| TS-X-001 |", [])],
)
def test_unit_spec_duplicate_detector_finds_a_repeated_id(text: str, expected: list[str]) -> None:
    """TS-IND-244: the detector itself reports repeats and ignores non-ID cells."""
    assert _duplicates(_first_cells(text + "\n| not an id | x |", r"TS-[A-Z]+-\d+")) == expected
