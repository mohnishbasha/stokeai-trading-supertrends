# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""scripts/regen-golden.sh and scripts/validate-fixtures.sh (TS-IND-243, TS-IND-248)."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "golden"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=ROOT, capture_output=True, text=True, check=False, timeout=300
    )


def _protected_digest() -> str:
    digest = hashlib.sha256()
    for sub in ("handcomputed", "tradingview"):
        for path in sorted((GOLDEN / sub).rglob("*")):
            if path.is_file():
                digest.update(path.name.encode() + path.read_bytes())
    return digest.hexdigest()


def test_unit_regen_golden_refuses_without_reason() -> None:
    """TS-IND-243: no `--reason` (or an empty one) exits non-zero and changes nothing."""
    before = {p: p.read_bytes() for p in GOLDEN.glob("*.sha256")}
    for args in ((), ("--reason",), ("--reason", "  ")):
        done = _run("scripts/regen-golden.sh", *args)
        assert done.returncode != 0
        assert "--reason" in done.stderr
    assert {p: p.read_bytes() for p in GOLDEN.glob("*.sha256")} == before


def test_unit_regen_golden_dry_run_reproduces_committed_hashes_and_spares_protected_files() -> None:
    """TS-IND-243: `--check` recomputes the hashes, matches the committed ones, writes nothing."""
    protected = _protected_digest()
    done = _run("scripts/regen-golden.sh", "--reason", "test", "--check")
    assert done.returncode == 0, done.stderr
    assert "synthetic_dataset" in done.stdout
    assert _protected_digest() == protected


def test_unit_validate_fixtures_checks_the_synthetic_dataset_hash() -> None:
    """TS-IND-248: scripts/validate-fixtures.sh passes on the committed hash."""
    done = _run("scripts/validate-fixtures.sh")
    assert done.returncode == 0, done.stdout + done.stderr
