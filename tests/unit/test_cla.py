# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""scripts/cla.py: CLA signature check and recording (S0-T08)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("cla", REPO / "scripts" / "cla.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["cla"] = module
    spec.loader.exec_module(module)
    return module


cla = _load()


@pytest.fixture
def signatures(tmp_path: Path) -> Path:
    path = tmp_path / "cla.json"
    path.write_text(json.dumps({"signedContributors": [{"name": "alice", "id": 1}]}))
    return path


def _check(author: str, signatures: Path) -> int:
    args = ["check", "--author", author, "--signatures", str(signatures)]
    return int(cla.main([*args, "--exempt", "mohnishbasha,dependabot[bot]"]))


def test_cla_check_passes_for_owner_and_dependabot(signatures: Path) -> None:
    assert _check("mohnishbasha", signatures) == 0
    assert _check("dependabot[bot]", signatures) == 0


def test_cla_check_passes_for_signed_contributor_case_insensitive(signatures: Path) -> None:
    assert _check("Alice", signatures) == 0


def test_cla_check_blocks_unsigned_contributor_with_instructions(
    signatures: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _check("mallory", signatures) == 1
    out = capsys.readouterr().out
    assert "mallory" in out
    assert cla.SIGN_PHRASE in out


def test_cla_check_blocks_when_signature_file_is_missing(tmp_path: Path) -> None:
    assert _check("mallory", tmp_path / "missing.json") == 1


@pytest.mark.parametrize(
    "body",
    [
        "I have read the CLA Document and I hereby sign the CLA",
        "  i have read the cla document and i hereby sign the cla.\n",
    ],
)
def test_cla_signature_phrase_is_recognized(body: str) -> None:
    assert cla.is_signature(body)


def test_cla_other_comments_are_not_signatures() -> None:
    assert not cla.is_signature("LGTM")
    assert not cla.is_signature("I have read the CLA Document")


def test_cla_sign_records_contributor_once(tmp_path: Path) -> None:
    path = tmp_path / "cla.json"
    args = ["sign", "--author", "bob", "--author-id", "7", "--pr", "12", "--comment-id", "99"]
    assert cla.main([*args, "--signatures", str(path)]) == 0
    assert cla.main([*args, "--signatures", str(path)]) == 0
    data = json.loads(path.read_text())["signedContributors"]
    assert len(data) == 1
    assert data[0]["name"] == "bob"
    assert data[0]["id"] == 7
    assert data[0]["pullRequestNo"] == 12
    assert data[0]["comment_id"] == 99


def test_cla_sign_ignores_comment_that_is_not_the_phrase(tmp_path: Path) -> None:
    path = tmp_path / "cla.json"
    args = ["sign", "--author", "bob", "--author-id", "7", "--pr", "12", "--comment-id", "99"]
    assert cla.main([*args, "--signatures", str(path), "--body", "please merge"]) == 0
    assert not path.exists()
