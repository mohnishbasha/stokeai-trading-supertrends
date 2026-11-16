# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Determinism hash and synthetic dataset hash (TS-IND-093, TS-IND-242, TS-ING-003).

The committed hashes are regenerated only with `scripts/regen-golden.sh --reason "..."` and
under the golden policy (TEST_PLAN 5.5). Indicator scope only: scoring joins in Sprint 3.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.golden import determinism

ROOT = Path(__file__).resolve().parents[2]


def _committed(name: str) -> str:
    return (determinism.GOLDEN_DIR / f"{name}.sha256").read_text(encoding="utf-8").strip()


def test_golden_fixture_provider_dataset_hash_matches_committed_hash() -> None:
    """TS-ING-003: the fixture dataset hash equals tests/golden/synthetic_dataset.sha256."""
    assert determinism.synthetic_dataset_hash() == _committed("synthetic_dataset")


def test_golden_indicators_determinism_hash_matches_committed_hash() -> None:
    """TS-IND-093: hash of every registered indicator output on the synthetic dataset."""
    assert determinism.determinism_hash() == _committed("determinism")


def test_unit_indicators_same_process_double_run_is_identical() -> None:
    """TS-IND-242: two runs in one process give the same hash."""
    assert determinism.determinism_hash() == determinism.determinism_hash()


@pytest.mark.parametrize(
    ("hashseed", "tz", "lang"),
    [("0", "UTC", "C"), ("12345", "Asia/Kolkata", "tr_TR.UTF-8")],
)
def test_golden_indicators_double_run_in_subprocess_with_other_environment(
    hashseed: str, tz: str, lang: str
) -> None:
    """TS-IND-242: separate processes, other PYTHONHASHSEED, TZ and LC_ALL, same hashes."""
    env = {**os.environ, "PYTHONHASHSEED": hashseed, "TZ": tz, "LC_ALL": lang, "LANG": lang}
    done = subprocess.run(
        [sys.executable, "-m", "tests.golden.determinism"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    got = dict(line.split() for line in done.stdout.splitlines())
    assert got == {
        "synthetic_dataset": _committed("synthetic_dataset"),
        "determinism": _committed("determinism"),
    }
