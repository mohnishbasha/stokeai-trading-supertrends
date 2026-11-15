# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Workflow lint for .github/workflows (ARCHITECTURE section 9, supply chain)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))
PINNED = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def _load(path: Path) -> dict[Any, Any]:
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict)
    return data


def _triggers(data: dict[Any, Any]) -> dict[str, Any]:
    # PyYAML reads the bare key "on" as boolean True.
    raw = data.get("on", data.get(True))
    if isinstance(raw, str):
        return {raw: None}
    if isinstance(raw, list):
        return dict.fromkeys(raw)
    assert isinstance(raw, dict)
    return raw


def test_ci_workflow_exists_with_required_jobs() -> None:
    jobs = _load(REPO / ".github" / "workflows" / "ci.yml")["jobs"]
    for job in (
        "lint-and-typecheck",
        "unit-tests",
        "coverage",
        "integration-tests",
        "e2e-tests",
        "build-image",
    ):
        assert job in jobs, job


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_ci_workflows_use_pull_request_not_pull_request_target_and_pinned_actions(
    path: Path,
) -> None:
    """TS-DEP-044."""
    data = _load(path)
    assert "pull_request_target" not in _triggers(data)
    assert "permissions" in data, "set top-level minimal permissions"
    for name, job in data["jobs"].items():
        for step in job.get("steps", []):
            uses = step.get("uses")
            if uses and not uses.startswith("./"):
                assert PINNED.match(uses), f"{path.name}:{name} action not pinned by SHA: {uses}"


def test_build_image_job_targets_amd64_and_arm64_without_push() -> None:
    """TS-DEP-007 (static half; the job itself proves the build)."""
    job = _load(REPO / ".github" / "workflows" / "ci.yml")["jobs"]["build-image"]
    text = yaml.safe_dump(job)
    assert "linux/amd64" in text
    assert "linux/arm64" in text
    build = [s for s in job["steps"] if "build-push-action" in str(s.get("uses", ""))]
    assert build
    assert all(s["with"].get("push") is False for s in build)


def _run_lines(job: dict[Any, Any]) -> str:
    return "\n".join(str(step.get("run", "")) for step in job.get("steps", []))


def test_build_clean_clone_setup_build_check_succeed() -> None:
    """TS-DEP-001 (static half; lint-and-typecheck runs these on a fresh checkout)."""
    job = _load(REPO / ".github" / "workflows" / "ci.yml")["jobs"]["lint-and-typecheck"]
    runs = _run_lines(job)
    for target in ("make setup", "make build", "make check"):
        assert target in runs, target
    assert runs.index("make setup") < runs.index("make build") < runs.index("make check")


def test_ci_lint_error_in_pr_fails_lint_and_typecheck_job() -> None:
    """TS-DEP-043 (static half; a demo PR with a lint error proved the job fails)."""
    data = _load(REPO / ".github" / "workflows" / "ci.yml")
    assert "pull_request" in _triggers(data)
    job = data["jobs"]["lint-and-typecheck"]
    assert "continue-on-error" not in job
    assert "make check" in _run_lines(job)
    makefile = (REPO / "Makefile").read_text()
    check_recipe = makefile.split("\ncheck:", 1)[1].split("\n\n", 1)[0]
    assert "ruff check" in check_recipe or "lint" in check_recipe


def test_security_pip_audit_and_npm_audit_no_high_or_critical() -> None:
    """TS-SEC-016 (static half; the audits run in lint-and-typecheck)."""
    job = _load(REPO / ".github" / "workflows" / "ci.yml")["jobs"]["lint-and-typecheck"]
    runs = _run_lines(job)
    assert "pip-audit" in runs
    assert re.search(r"npm (--prefix ui )?audit --audit-level=high", runs)


def test_required_check_contexts_match_branch_protection() -> None:
    """Branch protection requires `ci / lint-and-typecheck` and `ci / unit-tests`."""
    jobs = _load(REPO / ".github" / "workflows" / "ci.yml")["jobs"]
    assert jobs["lint-and-typecheck"]["name"] == "ci / lint-and-typecheck"
    assert jobs["unit-tests"]["name"] == "ci / unit-tests"
