# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Repository scripts and agent files (TEST_PLAN: Build and tooling scenarios)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

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


def test_scripts_stoke_inventory_no_kubeconfig_writes_unknown_rows_exit_0(tmp_path: Path) -> None:
    """TS-DEP-039."""
    out = tmp_path / "inv.md"
    env = {**os.environ, "KUBECONFIG": str(tmp_path / "missing"), "HOME": str(tmp_path)}
    result = _run([str(SCRIPTS / "stoke-inventory.sh"), str(out)], REPO, env)
    assert result.returncode == 0, result.stderr
    rows = [line for line in out.read_text().splitlines() if line.startswith("| ")][1:]
    assert len(rows) == 10
    assert all("UNKNOWN: run against the cluster" in row for row in rows)


def test_scripts_stoke_inventory_is_read_only_only_get_commands_issued(tmp_path: Path) -> None:
    """TS-DEP-040: against a reachable (fake) cluster every kubectl and flux call is a get."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    for tool in ("kubectl", "flux"):
        fake = bin_dir / tool
        fake.write_text(
            "#!/usr/bin/env bash\n"
            f'echo "{tool} $*" >> "{log}"\n'
            'case "$*" in\n'
            '  *"--raw /version"*) echo \'{"gitVersion":"v1.31.0+k3s1"}\' ;;\n'
            '  *"-o json"*) echo \'{"items":[]}\' ;;\n'
            "esac\n"
        )
        fake.chmod(0o755)
    kubeconfig = tmp_path / "kubeconfig"
    kubeconfig.write_text("apiVersion: v1\n")
    out = tmp_path / "inv.md"
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "KUBECONFIG": str(kubeconfig)}
    result = _run([str(SCRIPTS / "stoke-inventory.sh"), str(out)], REPO, env)
    assert result.returncode == 0, result.stderr
    calls = log.read_text().splitlines()
    assert calls
    assert all(c.split()[1] == "get" for c in calls), calls
    text = out.read_text()
    assert "v1.31.0+k3s1" in text
    assert "UNKNOWN" not in text


def test_repo_private_directory_and_logs_are_git_ignored_and_untracked() -> None:
    """TS-DEP-041."""
    for path in ("private/STOKE_INVENTORY.md", "logs/run.log"):
        assert _run(["git", "check-ignore", "-q", path], REPO).returncode == 0, path
    tracked = _run(["git", "ls-files", "private", "logs"], REPO).stdout
    assert tracked == ""


def test_repo_operator_files_runner_mk_and_run_scripts_not_ignored_and_untouched() -> None:
    """TS-DEP-042: the operator's runner files stay visible to git and are never committed."""
    for name in RUNNER_FILES:
        assert _run(["git", "check-ignore", "-q", name], REPO).returncode == 1, name
        assert _run(["git", "ls-files", "--error-unmatch", name], REPO).returncode != 0, name


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck not installed")
def test_scripts_shellcheck_passes_for_all_scripts() -> None:
    """TS-DEP-038."""
    scripts = [str(p) for p in SCRIPTS.glob("*.sh")]
    scripts += [str(p) for p in (REPO / ".agent" / "skills").glob("*/run.sh")]
    result = _run(["shellcheck", *scripts], REPO)
    assert result.returncode == 0, result.stdout


def test_shell_scripts_use_strict_mode() -> None:
    for path in [*SCRIPTS.glob("*.sh"), *(REPO / ".agent" / "skills").glob("*/run.sh")]:
        assert "set -euo pipefail" in path.read_text(), path
        assert os.access(path, os.X_OK), path


def test_security_spdx_header_check_passes_on_repo() -> None:
    result = _run([str(SCRIPTS / "check-spdx.sh")], REPO)
    assert result.returncode == 0, result.stdout


def test_security_spdx_header_check_fails_on_source_file_without_header(tmp_path: Path) -> None:
    """TS-SEC-018."""
    bad = tmp_path / "bad.py"
    bad.write_text("print('hi')\n")
    result = _run([str(SCRIPTS / "check-spdx.sh"), str(bad)], REPO)
    assert result.returncode == 1
    assert "bad.py" in result.stdout


def test_env_example_is_committed_not_ignored() -> None:
    assert _run(["git", "check-ignore", "-q", ".env.example"], REPO).returncode == 1


@pytest.mark.parametrize(("skill", "target"), [("run-tests", "test"), ("check-types", "check")])
def test_agent_skills_run_tests_and_check_types_run_sh_exit_0(
    skill: str, target: str, tmp_path: Path
) -> None:
    """TS-MCP-020: each run.sh runs its make target from the repo root and exits 0.

    A fake make records the call; running the real target here would recurse into pytest.
    """
    directory = REPO / ".agent" / "skills" / skill
    assert (directory / "SKILL.md").is_file()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "make.log"
    fake = bin_dir / "make"
    fake.write_text(f'#!/usr/bin/env bash\necho "$PWD $*" >> "{log}"\n')
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    result = _run([str(directory / "run.sh")], tmp_path, env)
    assert result.returncode == 0, result.stderr
    assert log.read_text().split() == [str(REPO), target]


def test_claude_md_imports_agents_md() -> None:
    first = (REPO / "CLAUDE.md").read_text().splitlines()[0]
    assert first == "@import AGENTS.md"


def test_soul_md_has_no_build_commands_or_paths() -> None:
    text = (REPO / "SOUL.md").read_text()
    assert not re.search(r"\bmake (setup|build|check|test|coverage|up|down|smoke|image)\b", text)
    assert "`" not in text
    assert "scripts/" not in text
    assert text.count("NEVER") + text.lower().count("never ") >= 8
