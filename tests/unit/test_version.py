# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Version and CLI --version scenarios (TS-CLI-001)."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from supertrends import version
from supertrends.cli.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_version_get_version_env_overrides_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERTRENDS_VERSION", "9.9.9")
    assert version.get_version() == "9.9.9"


def test_version_get_version_matches_version_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPERTRENDS_VERSION", raising=False)
    assert version.get_version() == (REPO_ROOT / "VERSION").read_text().strip()


def test_version_get_commit_env_overrides_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERTRENDS_COMMIT", "abc1234")
    assert version.get_commit() == "abc1234"


def test_version_get_commit_without_git_returns_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SUPERTRENDS_COMMIT", raising=False)
    monkeypatch.setattr(version, "_SOURCE_DIR", tmp_path)
    monkeypatch.setenv("PATH", "")
    assert version.get_commit() == "unknown"


def test_cli_version_prints_version_and_commit_and_license_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERTRENDS_VERSION", "0.1.0")
    monkeypatch.setenv("SUPERTRENDS_COMMIT", "abc1234")
    monkeypatch.setenv("SUPERTRENDS_SOURCE_URL", "https://example.test/src")
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert lines[0] == "supertrends 0.1.0 (abc1234)"
    assert lines[1] == (
        "Copyright Serverless Ventures LLC. Noncommercial use only. https://example.test/src"
    )
