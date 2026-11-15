# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Repository scripts and agent files (TEST_PLAN: Build and tooling scenarios)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
RUNNER_FILES = ("runner.mk", "run-supertrends.sh", "run-supertrends-status.sh")


def _run(
    args: list[str], cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _copy_version_files(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "ui").mkdir()
    shutil.copy(SCRIPTS / "check-versions.sh", tmp_path / "scripts")
    shutil.copy(REPO / "VERSION", tmp_path)
    shutil.copy(REPO / "ui" / "package.json", tmp_path / "ui")
    return tmp_path


def test_version_check_script_passes_when_all_files_agree() -> None:
    """TS-DEP-002."""
    result = _run([str(SCRIPTS / "check-versions.sh")], REPO)
    assert result.returncode == 0, result.stdout
    assert "All versions consistent" in result.stdout


def test_version_check_script_fails_naming_ui_package_json_on_mismatch(tmp_path: Path) -> None:
    """TS-DEP-003."""
    root = _copy_version_files(tmp_path)
    pkg = root / "ui" / "package.json"
    data = json.loads(pkg.read_text())
    data["version"] = "9.9.9"
    pkg.write_text(json.dumps(data))
    result = _run([str(root / "scripts" / "check-versions.sh")], root)
    assert result.returncode == 1
    assert "ui/package.json" in result.stdout
    assert "9.9.9" in result.stdout


def test_check_versions_rejects_non_semver(tmp_path: Path) -> None:
    root = _copy_version_files(tmp_path)
    (root / "VERSION").write_text("v1.0\n")
    result = _run([str(root / "scripts" / "check-versions.sh")], root)
    assert result.returncode == 1
    assert "not semver" in result.stdout


def test_check_versions_checks_chart_once_it_exists(tmp_path: Path) -> None:
    root = _copy_version_files(tmp_path)
    chart = root / "deploy" / "helm" / "stokeai-supertrends"
    chart.mkdir(parents=True)
    (chart / "Chart.yaml").write_text('version: 0.1.0\nappVersion: "0.0.9"\n')
    result = _run([str(root / "scripts" / "check-versions.sh")], root)
    assert result.returncode == 1
    assert "Chart.yaml appVersion" in result.stdout


def test_version_sync_writes_checked_files(tmp_path: Path) -> None:
    root = _copy_version_files(tmp_path)
    shutil.copy(SCRIPTS / "version-sync.sh", root / "scripts")
    (root / "VERSION").write_text("0.2.0\n")
    assert _run([str(root / "scripts" / "version-sync.sh")], root).returncode == 0
    assert json.loads((root / "ui" / "package.json").read_text())["version"] == "0.2.0"
    assert _run([str(root / "scripts" / "check-versions.sh")], root).returncode == 0


def test_changelog_extract_script_returns_section_for_version(tmp_path: Path) -> None:
    """TS-DEP-004."""
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n- next\n\n## [0.2.0] - 2026-01-02\n\n"
        "### Added\n\n- feature two\n\n## [0.1.0] - 2026-01-01\n\n- feature one\n"
    )
    result = _run([str(SCRIPTS / "extract-changelog.sh"), "0.2.0"], tmp_path)
    assert result.returncode == 0
    assert "feature two" in result.stdout
    assert "feature one" not in result.stdout
    assert "next" not in result.stdout


def test_changelog_has_unreleased_section() -> None:
    assert "## [Unreleased]" in (REPO / "CHANGELOG.md").read_text()


def test_shell_scripts_use_strict_mode() -> None:
    for path in [*SCRIPTS.glob("*.sh"), *(REPO / ".agent" / "skills").glob("*/run.sh")]:
        assert "set -euo pipefail" in path.read_text(), path
        assert os.access(path, os.X_OK), path
