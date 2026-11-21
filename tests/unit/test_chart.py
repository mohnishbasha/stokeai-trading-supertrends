# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Helm chart render tests (ARCHITECTURE section 10.6, S3-T11).

Renders deploy/helm/stokeai-supertrends with `helm template` (no cluster, no network).
CI installs helm in the unit-tests job, so a missing helm fails there instead of skipping.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
CHART = REPO / "deploy" / "helm" / "stokeai-supertrends"
POSTGRES_DIGEST = "sha256:40865bc877a289da75963d97d72b59633f639fc5af7a4e856bfa3714cae5b536"

pytestmark = pytest.mark.skipif(
    shutil.which("helm") is None and not os.environ.get("CI"),
    reason="helm is not installed; install helm 3.16+ to run chart render tests (CI always has it)",
)

Doc = dict[str, Any]


def render(profile: str | None, *sets: str) -> list[Doc]:
    cmd = ["helm", "template", "supertrends", str(CHART), "-n", "supertrends"]
    if profile:
        cmd += ["-f", str(CHART / f"values-{profile}.yaml")]
    for item in sets:
        cmd += ["--set", item]
    out = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stderr
    return [d for d in yaml.safe_load_all(out.stdout) if d]


def of_kind(docs: list[Doc], kind: str) -> list[Doc]:
    return [d for d in docs if d["kind"] == kind]


def one(docs: list[Doc], kind: str, name_part: str = "") -> Doc:
    found = [d for d in of_kind(docs, kind) if name_part in d["metadata"]["name"]]
    assert len(found) == 1, (kind, name_part, [d["metadata"]["name"] for d in docs])
    return found[0]


def api_service(docs: list[Doc]) -> Doc:
    return next(d for d in of_kind(docs, "Service") if d["metadata"]["name"] == "supertrends")


def pod_specs(docs: list[Doc]) -> list[tuple[str, Doc]]:
    specs: list[tuple[str, Doc]] = []
    for d in docs:
        name = f"{d['kind']}/{d['metadata']['name']}"
        if d["kind"] in ("Deployment", "StatefulSet", "Job"):
            specs.append((name, d["spec"]["template"]["spec"]))
        elif d["kind"] == "CronJob":
            specs.append((name, d["spec"]["jobTemplate"]["spec"]["template"]["spec"]))
        elif d["kind"] == "Pod":
            specs.append((name, d["spec"]))
    return specs


def test_chart_version_and_app_version_equal_version_file() -> None:
    """TS-DEP-101: Chart.yaml version and appVersion equal VERSION."""
    version = (REPO / "VERSION").read_text().strip()
    chart = yaml.safe_load((CHART / "Chart.yaml").read_text())
    assert chart["version"] == version
    assert chart["appVersion"] == version
    assert chart["name"] == "stokeai-supertrends"


@pytest.mark.parametrize("profile", [None, "kind"])
def test_chart_daily_run_cronjob_schedule_timezone_forbid(profile: str | None) -> None:
    """TS-DEP-102: CronJob runs `supertrends run daily` at 17:30 ET weekdays, never overlapping."""
    cron = one(render(profile), "CronJob")
    spec = cron["spec"]
    assert spec["schedule"] == "30 17 * * 1-5"
    assert spec["timeZone"] == "America/New_York"
    assert spec["concurrencyPolicy"] == "Forbid"
    assert spec["startingDeadlineSeconds"] == 3600
    pod = spec["jobTemplate"]["spec"]["template"]["spec"]
    assert pod["containers"][0]["command"] == ["supertrends"]
    assert pod["containers"][0]["args"] == ["run", "daily"]
    assert pod["restartPolicy"] == "Never"


def test_chart_daily_run_can_be_suspended_or_disabled() -> None:
    """TS-DEP-103: dailyRun.suspend and dailyRun.enabled are honoured."""
    assert one(render("kind", "dailyRun.suspend=true"), "CronJob")["spec"]["suspend"] is True
    assert of_kind(render("kind", "dailyRun.enabled=false"), "CronJob") == []


@pytest.mark.parametrize("profile", [None, "kind"])
def test_chart_every_workload_is_hardened(profile: str | None) -> None:
    """TS-DEP-104: non-root 10001, read-only root fs, no caps, seccomp, no privilege escalation."""
    specs = pod_specs(render(profile))
    assert any(n.startswith("Deployment/") for n, _ in specs)
    for name, spec in specs:
        if "postgres" in name:
            continue  # the bundled database image runs as its own uid (next test)
        pod = spec["securityContext"]
        assert pod["runAsNonRoot"] is True, name
        assert pod["runAsUser"] == 10001, name
        assert pod["seccompProfile"] == {"type": "RuntimeDefault"}, name
        assert spec["automountServiceAccountToken"] is False, name
        for c in spec["containers"] + spec.get("initContainers", []):
            sc = c["securityContext"]
            assert sc["readOnlyRootFilesystem"] is True, (name, c["name"])
            assert sc["allowPrivilegeEscalation"] is False, (name, c["name"])
            assert sc["capabilities"] == {"drop": ["ALL"]}, (name, c["name"])
            assert c["resources"]["requests"], (name, c["name"])
            assert c["resources"]["limits"], (name, c["name"])


def test_chart_postgres_pod_drops_caps_and_forbids_escalation() -> None:
    """TS-DEP-105: the bundled Postgres pod is non-root, drops ALL caps, seccomp RuntimeDefault."""
    sts = one(render("kind"), "StatefulSet")
    spec = sts["spec"]["template"]["spec"]
    assert spec["securityContext"]["runAsNonRoot"] is True
    assert spec["securityContext"]["seccompProfile"] == {"type": "RuntimeDefault"}
    sc = spec["containers"][0]["securityContext"]
    assert sc["allowPrivilegeEscalation"] is False
    assert sc["capabilities"] == {"drop": ["ALL"]}
    assert spec["containers"][0]["resources"]["limits"]


def test_chart_api_deployment_probes_tmp_and_rolling_update() -> None:
    """TS-DEP-106: probes on /healthz and /readyz, /tmp emptyDir, zero-unavailable rollout."""
    dep = one(render("kind"), "Deployment")
    assert dep["spec"]["strategy"]["rollingUpdate"] == {"maxUnavailable": 0, "maxSurge": 1}
    spec = dep["spec"]["template"]["spec"]
    container = spec["containers"][0]
    assert container["readinessProbe"]["httpGet"]["path"] == "/readyz"
    assert container["livenessProbe"]["httpGet"]["path"] == "/healthz"
    assert container["startupProbe"]["httpGet"]["path"] == "/healthz"
    assert {"name": "tmp", "mountPath": "/tmp"} in container["volumeMounts"]  # noqa: S108
    assert {"name": "tmp", "emptyDir": {}} in spec["volumes"]
    assert container["args"] == ["serve", "--bind", "0.0.0.0:8080"]


def test_chart_api_service_and_allowed_hosts() -> None:
    """TS-DEP-107: Service exposes 8080; allowed hosts include the in-cluster DNS names."""
    docs = render("kind")
    svc = api_service(docs)
    assert svc["spec"]["ports"][0]["port"] == 8080
    container = one(docs, "Deployment")["spec"]["template"]["spec"]["containers"][0]
    env = {e["name"]: e.get("value") for e in container["env"]}
    hosts = env["SUPERTRENDS_ALLOWED_HOSTS"].split(",")
    for expected in (
        "localhost",
        "127.0.0.1",
        "supertrends",
        "supertrends.supertrends",
        "supertrends.supertrends.svc",
        "supertrends.supertrends.svc.cluster.local",
    ):
        assert expected in hosts


def test_chart_migration_job_is_a_pre_install_pre_upgrade_hook_that_waits_for_postgres() -> None:
    """TS-DEP-108: migration Job hook annotations, `db migrate`, waits for Postgres."""
    job = one(render("kind"), "Job", "migrate")
    ann = job["metadata"]["annotations"]
    assert ann["helm.sh/hook"] == "pre-install,pre-upgrade"
    assert ann["helm.sh/hook-delete-policy"] == "before-hook-creation,hook-succeeded"
    spec = job["spec"]["template"]["spec"]
    assert spec["containers"][0]["command"] == ["supertrends"]
    assert spec["containers"][0]["args"] == ["db", "migrate"]
    wait = spec["initContainers"][0]
    assert "pg_isready" in " ".join(wait["command"] + wait.get("args", []))


def test_chart_bundled_postgres_resources_are_hooks_ordered_before_the_migration() -> None:
    """TS-DEP-109: bundled Postgres Secret, Service, StatefulSet precede the migration."""
    docs = render("kind")
    weights: dict[str, int] = {}
    for d in docs:
        ann = d["metadata"].get("annotations", {})
        if ann.get("helm.sh/hook") and d["kind"] in ("Secret", "Service", "StatefulSet", "Job"):
            weights[d["kind"] + "/" + d["metadata"]["name"]] = int(ann["helm.sh/hook-weight"])
    migrate = next(w for n, w in weights.items() if n.startswith("Job/") and "migrate" in n)
    for kind in ("Secret", "Service", "StatefulSet"):
        assert next(w for n, w in weights.items() if n.startswith(kind + "/")) < migrate, kind
    assert one(docs, "StatefulSet")["metadata"]["annotations"]["helm.sh/hook"] == "pre-install"


def test_chart_bundled_postgres_only_in_kind_profile() -> None:
    """TS-DEP-110: defaults render no Postgres; kind renders it."""
    default = render(None)
    assert of_kind(default, "StatefulSet") == []
    assert [d for d in of_kind(default, "Service") if "postgres" in d["metadata"]["name"]] == []
    kind = render("kind")
    image = one(kind, "StatefulSet")["spec"]["template"]["spec"]["containers"][0]["image"]
    assert image == f"postgres:17-bookworm@{POSTGRES_DIGEST}"
    assert one(kind, "Service", "postgres")["spec"]["ports"][0]["port"] == 5432


def test_chart_postgres_digest_matches_ci_and_compose() -> None:
    """TS-DEP-111: the chart, CI service container, and Compose pin the same Postgres digest."""
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    compose = (REPO / "deploy" / "compose" / "docker-compose.local.yml").read_text()
    values = (CHART / "values-kind.yaml").read_text()
    for text in (ci, compose, values):
        assert POSTGRES_DIGEST in text


def test_chart_generated_secret_only_with_bundled_postgres() -> None:
    """TS-DEP-112: the chart creates a Secret only when bundled Postgres is on."""
    assert of_kind(render(None), "Secret") == []
    secret = one(render("kind"), "Secret")
    assert set(secret["stringData"]) >= {
        "POSTGRES_PASSWORD",
        "SUPERTRENDS_DATABASE_URL",
        "SUPERTRENDS_API_TOKEN",
    }
    assert secret["metadata"]["annotations"]["helm.sh/hook"] == "pre-install"
    url = secret["stringData"]["SUPERTRENDS_DATABASE_URL"]
    assert url.startswith("postgresql+psycopg://supertrends:")
    assert secret["stringData"]["POSTGRES_PASSWORD"] in url
    assert secret["stringData"]["SUPERTRENDS_API_TOKEN"] != "dev-token"  # noqa: S105


def test_chart_default_values_read_credentials_from_existing_secret() -> None:
    """TS-DEP-113: production-like defaults take every credential from an existing Secret."""
    for name, spec in pod_specs(render(None)):
        if name.startswith("Pod/"):
            continue
        refs = [
            e["secretRef"]["name"]
            for c in spec["containers"]
            for e in c.get("envFrom", [])
            if "secretRef" in e
        ]
        assert refs == ["supertrends-secrets"], name


def test_chart_values_files_hold_no_secret_data() -> None:
    """TS-DEP-114: no values file carries a literal password, token, or key."""
    secret_key = re.compile(r"(password|token|apikey|api_key|secret)$", re.IGNORECASE)

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if secret_key.search(str(key)) and isinstance(value, str):
                    assert value == "" or key == "existingSecret", f"{path}.{key} holds a literal"
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")

    files = sorted(CHART.glob("values*.yaml"))
    assert len(files) >= 2
    for values in files:
        walk(yaml.safe_load(values.read_text()), values.name)
        assert "kind: Secret" not in values.read_text()


def test_chart_kind_profile_uses_fixture_provider_and_local_image() -> None:
    """TS-DEP-115: kind runs the fixture providers, template narratives, and a kind-loaded image."""
    docs = render("kind", "image.tag=9.9.9")
    seen = 0
    for _, spec in pod_specs(docs):
        for c in spec["containers"] + spec.get("initContainers", []):
            if "stokeai-supertrends" in c["image"]:
                seen += 1
                assert c["image"].endswith(":9.9.9")
                assert c["imagePullPolicy"] in ("IfNotPresent", "Never")
    assert seen >= 3  # API, CronJob, migration Job (and the helm test Pod)
    cron = one(docs, "CronJob")["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]
    env = {e["name"]: e.get("value") for e in cron["env"]}
    assert env["SUPERTRENDS_MARKET_PROVIDER"] == "fixture"
    assert env["SUPERTRENDS_FUNDAMENTALS_PROVIDER"] == "fixture"
    assert env["SUPERTRENDS_NARRATIVE_PROVIDER"] == "template"
    assert env["SUPERTRENDS_ENV"] == "ci"


def test_chart_kind_service_is_nodeport_30080_matching_kind_cluster_config() -> None:
    """TS-DEP-116: kind exposes the API on NodePort 30080, mapped to the host by cluster.yaml."""
    svc = api_service(render("kind"))
    assert svc["spec"]["type"] == "NodePort"
    assert svc["spec"]["ports"][0]["nodePort"] == 30080
    cluster = yaml.safe_load((REPO / "deploy" / "kind" / "cluster.yaml").read_text())
    mapping = cluster["nodes"][0]["extraPortMappings"][0]
    assert mapping["containerPort"] == 30080
    assert mapping["listenAddress"] == "127.0.0.1"
    assert mapping["protocol"] == "TCP"


def test_chart_kind_cluster_node_image_pinned_by_digest() -> None:
    """TS-DEP-117: the kind node image is pinned by tag and digest."""
    cluster = yaml.safe_load((REPO / "deploy" / "kind" / "cluster.yaml").read_text())
    image = cluster["nodes"][0]["image"]
    assert re.fullmatch(r"kindest/node:v\d+\.\d+\.\d+@sha256:[0-9a-f]{64}", image), image


def test_chart_helm_test_pod_checks_readyz_from_inside_the_cluster() -> None:
    """TS-DEP-118: `helm test` Pod calls the Service /readyz and is hardened."""
    pod = one(render("kind"), "Pod")
    assert pod["metadata"]["annotations"]["helm.sh/hook"] == "test"
    assert pod["spec"]["restartPolicy"] == "Never"
    c = pod["spec"]["containers"][0]
    line = " ".join(c.get("command", []) + c.get("args", []))
    assert "healthcheck" in line
    assert "http://supertrends:8080" in line


def test_chart_helm_lint_passes_for_default_and_kind_profiles() -> None:
    """TS-DEP-119: `helm lint` is clean for the default values and values-kind.yaml."""
    for profile in (None, "kind"):
        cmd = ["helm", "lint", str(CHART)]
        if profile:
            cmd += ["-f", str(CHART / f"values-{profile}.yaml")]
        out = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert out.returncode == 0, out.stdout + out.stderr


def test_chart_requests_no_gpu() -> None:
    """TS-DEP-120: no workload requests a GPU (CPU-only product)."""
    for profile in (None, "kind"):
        text = json.dumps(render(profile)).lower()
        assert "nvidia.com" not in text
        assert "gpu" not in text
