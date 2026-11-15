# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""`supertrends healthcheck` exit codes (ARCHITECTURE section 6, CLI table)."""

import httpx
import pytest
from typer.testing import CliRunner

from supertrends.cli import main as cli_main
from supertrends.cli.main import app


def _patch_get(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    real_client = httpx.Client

    def fake_client(**kwargs: object) -> httpx.Client:
        return real_client(transport=handler)

    monkeypatch.setattr(cli_main.httpx, "Client", fake_client)


def test_cli_healthcheck_ready_exits_0(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_get(monkeypatch, httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    result = CliRunner().invoke(app, ["healthcheck", "--url", "http://app:8080"])
    assert result.exit_code == 0
    assert result.output.strip() == "ok"


def test_cli_healthcheck_not_ready_exits_3(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_get(monkeypatch, httpx.MockTransport(lambda r: httpx.Response(503, json={})))
    result = CliRunner().invoke(app, ["healthcheck", "--url", "http://app:8080"])
    assert result.exit_code == 3


def test_cli_healthcheck_unreachable_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    _patch_get(monkeypatch, httpx.MockTransport(refuse))
    result = CliRunner().invoke(app, ["healthcheck", "--url", "http://app:8080"])
    assert result.exit_code == 1
