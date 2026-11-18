# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Makefile kind targets, Dockerfile runtime shape, and kind-e2e workflow (S3-T11)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]


def make_dry_run(target: str, *args: str, env: dict[str, str] | None = None) -> str:
    base = {
        k: v for k, v in os.environ.items() if k not in ("SUPERTRENDS_HOST_PORT", "SMOKE_BASE_URL")
    }
    out = subprocess.run(
        ["make", "-n", target, *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
        env={**base, **(env or {})},
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


def ci_jobs() -> dict[str, Any]:
    data = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text())
    jobs: dict[str, Any] = data["jobs"]
    return jobs


def step_index(job: dict[str, Any], needle: str) -> int:
    for i, step in enumerate(job["steps"]):
        if needle in (step.get("run", "") + step.get("uses", "") + step.get("name", "")):
            return i
    raise AssertionError(f"no step containing {needle!r}")


def test_make_kind_up_creates_cluster_from_config_with_overridable_host_port() -> None:
    """TS-DEP-121: kind-up uses deploy/kind/cluster.yaml, cluster name, and the host port."""
    out = make_dry_run("kind-up", "SUPERTRENDS_HOST_PORT=56411", "KIND_CLUSTER=st-x")
    assert "kind create cluster --name st-x" in out
    assert "deploy/kind/cluster.yaml" in out
    assert "56411" in out
    assert "not available" not in out


def test_make_kind_load_helm_install_test_down_are_implemented() -> None:
    """TS-DEP-122: kind-load, helm-install (profile kind, --wait), helm-test, kind-down recipes."""
    load = make_dry_run("kind-load", "KIND_CLUSTER=st-x")
    assert "kind load docker-image" in load
    assert "--name st-x" in load
    install = make_dry_run("helm-install", "RELEASE=rel", "NAMESPACE=ns")
    assert "helm upgrade --install rel" in install
    assert "--wait" in install
    assert "-n ns" in install
    assert "values-kind.yaml" in install
    assert "image.repository=" in install
    assert "image.tag=0.1.0" in install
    test = make_dry_run("helm-test", "RELEASE=rel", "NAMESPACE=ns")
    assert "helm test rel" in test
    assert "-n ns" in test
    down = make_dry_run("kind-down", "KIND_CLUSTER=st-x")
    assert "kind delete cluster --name st-x" in down
    for out in (install, test, down):
        assert "not available" not in out


def test_make_helm_install_profile_selects_values_file() -> None:
    """TS-DEP-123: PROFILE picks values-<profile>.yaml."""
    assert "values-selfhost.yaml" in make_dry_run("helm-install", "PROFILE=selfhost")


def test_make_smoke_base_url_defaults_from_host_port() -> None:
    """TS-DEP-124: SUPERTRENDS_HOST_PORT sets the smoke URL; explicit SMOKE_BASE_URL still wins."""
    assert "SMOKE_BASE_URL=http://localhost:56411" in make_dry_run(
        "smoke", env={"SUPERTRENDS_HOST_PORT": "56411"}
    )
    assert "SMOKE_BASE_URL=http://localhost:8080" in make_dry_run("smoke")
    assert "SMOKE_BASE_URL=http://x:1" in make_dry_run(
        "smoke", env={"SUPERTRENDS_HOST_PORT": "56411", "SMOKE_BASE_URL": "http://x:1"}
    )


def test_dockerfile_runs_serve_as_uid_10001() -> None:
    """TS-DEP-125: the image runs `supertrends serve` as 10001 and ships the migrations."""
    text = (REPO / "Dockerfile").read_text()
    assert "USER 10001:10001" in text
    assert 'ENTRYPOINT ["supertrends"]' in text
    assert 'CMD ["serve", "--bind", "0.0.0.0:8080"]' in text
    assert "COPY --from=build /app/migrations /app/migrations" in text


def test_ci_kind_e2e_job_runs_the_whole_loop() -> None:
    """TS-DEP-126: kind-e2e lints, builds, creates a kind cluster, installs, helm-tests, smokes."""
    job = ci_jobs()["kind-e2e"]
    assert job["name"] == "ci / kind-e2e"
    order = [
        "make helm-lint",
        "make image",
        "make kind-up",
        "make kind-load",
        "make helm-install",
        "make helm-test",
        "make smoke",
    ]
    idx = [step_index(job, n) for n in order]
    assert idx == sorted(idx), "steps out of order"
    assert "SUPERTRENDS_HOST_PORT" in yaml.safe_dump(job)


def test_ci_kind_e2e_actions_are_pinned_and_tool_versions_set() -> None:
    """TS-DEP-127: kind and helm are installed by SHA-pinned actions with explicit versions."""
    job = ci_jobs()["kind-e2e"]
    uses = [s["uses"] for s in job["steps"] if "uses" in s]
    assert any(u.startswith("helm/kind-action@") for u in uses)
    assert any(u.lower().startswith("azure/setup-helm@") for u in uses)
    kind_step = next(s for s in job["steps"] if s.get("uses", "").startswith("helm/kind-action@"))
    assert kind_step["with"]["install_only"] is True
    assert str(kind_step["with"]["version"]).startswith("v0.")


def test_ci_kind_e2e_collects_diagnostics_on_failure() -> None:
    """TS-DEP-128: a failed kind loop dumps pods, events, and logs."""
    job = ci_jobs()["kind-e2e"]
    diag = [s for s in job["steps"] if s.get("if") == "failure()"]
    assert diag
    assert "kubectl" in diag[0]["run"]


def test_ci_unit_tests_run_with_outbound_network_blocked_at_the_os_level() -> None:
    """TS-DEP-046, TS-DEP-129: iptables and ip6tables allow loopback, drop the rest, before pytest."""
    job = ci_jobs()["unit-tests"]
    block = step_index(job, "iptables")
    run = job["steps"][block]["run"]
    for tool in ("iptables", "ip6tables"):
        assert f"{tool} -A OUTPUT -o lo -j ACCEPT" in run
        assert f"{tool} -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT" in run
        assert f"{tool} -A OUTPUT -j REJECT" in run
    assert "curl" in run, "the step proves the block before the tests run"
    assert block < step_index(job, "make test")
    assert block > step_index(job, "npm --prefix ui run build")
