# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Container hardening and the Compose loop (TS-DEP-005, TS-DEP-006).

Runs only when SUPERTRENDS_IT_IMAGE names a locally loaded image (CI build-image job, or
locally after "make image"). Talks only to containers on this host.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx
import pytest

REPO = Path(__file__).resolve().parents[2]
IMAGE = os.environ.get("SUPERTRENDS_IT_IMAGE", "")
COMPOSE = REPO / "deploy" / "compose" / "docker-compose.local.yml"
HOST_PORT = os.environ.get("SUPERTRENDS_HOST_PORT", "18080")

pytestmark = pytest.mark.skipif(
    not IMAGE or shutil.which("docker") is None,
    reason="set SUPERTRENDS_IT_IMAGE to a loaded image to run container tests",
)


def _docker(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_it_image_runs_as_non_root_uid_10001_read_only_root_fs() -> None:
    config = json.loads(_docker("image", "inspect", IMAGE).stdout)[0]["Config"]
    assert config["User"] == "10001:10001"
    assert config["Healthcheck"]["Test"][0] == "CMD"  # exec form, no shell
    uid = _docker("run", "--rm", "--read-only", "--entrypoint", "id", IMAGE, "-u")
    assert uid.stdout.strip() == "10001"
    write = _docker(
        "run", "--rm", "--read-only", "--entrypoint", "python", IMAGE,
        "-c", "open('/app/probe', 'w')",
    )  # fmt: skip
    assert write.returncode != 0
    assert "Read-only file system" in write.stderr
    version = _docker("run", "--rm", "--read-only", IMAGE, "--version")
    assert version.returncode == 0
    assert version.stdout.startswith("supertrends ")


def test_it_image_compose_up_healthz_returns_ok_then_down_cleans_volumes() -> None:
    image, _, version = IMAGE.rpartition(":")
    env = {**os.environ, "IMAGE": image, "VERSION": version, "SUPERTRENDS_HOST_PORT": HOST_PORT}
    compose = ["compose", "-f", str(COMPOSE)]
    try:
        up = _docker(*compose, "up", "-d", "--wait", env=env)
        assert up.returncode == 0, up.stderr
        body: dict[str, str] = {}
        for _ in range(30):
            try:
                body = httpx.get(f"http://127.0.0.1:{HOST_PORT}/healthz", timeout=2).json()
                break
            except httpx.HTTPError:
                time.sleep(1)
        assert body.get("status") == "ok"
    finally:
        down = _docker(*compose, "down", "-v", env=env)
    assert down.returncode == 0, down.stderr
    volumes = _docker("volume", "ls", "-q", "--filter", "name=supertrends-local").stdout
    assert volumes.strip() == ""
