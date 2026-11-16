# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""`supertrends ingest` argument handling and exit codes (ARCHITECTURE section 6.2)."""

from datetime import date
from typing import Any

import pytest
from sqlalchemy.exc import OperationalError
from typer.testing import CliRunner

from supertrends.cli.main import app
from supertrends.data import ingest as ingest_module
from supertrends.data.ingest import IngestSummary, TickerResult
from supertrends.errors import IngestError


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERTRENDS_DATABASE_URL", "postgresql://u:p@127.0.0.1:1/none")
    monkeypatch.setenv("SUPERTRENDS_MARKET_PROVIDER", "fixture")
    monkeypatch.setenv("SUPERTRENDS_FUNDAMENTALS_PROVIDER", "fixture")
    monkeypatch.setenv("SUPERTRENDS_FIXTURE_END_DATE", "2026-11-13")


def test_unit_cli_ingest_invalid_date_exits_2() -> None:
    result = CliRunner().invoke(app, ["ingest", "--date", "yesterday"])
    assert result.exit_code == 2
    assert "invalid --date" in result.output


def test_unit_cli_ingest_invalid_symbol_exits_2() -> None:
    result = CliRunner().invoke(app, ["ingest", "--symbols", "FXA,bad symbol!"])
    assert result.exit_code == 2
    assert "invalid symbol" in result.output


def test_unit_cli_ingest_prints_per_ticker_summary_and_quality_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    def fake(_engine: Any, _market: Any, _fund: Any, symbols: Any, **kwargs: Any) -> IngestSummary:
        seen.update(symbols=list(symbols), **kwargs)
        return IngestSummary(
            date(2026, 11, 13),
            "fixture",
            [
                TickerResult("FXA", daily_rows=756, quality="ok"),
                TickerResult("FXE", split_refetch=True, quality="degraded"),
                TickerResult("NOPE", status="unresolved"),
            ],
        )

    monkeypatch.setattr(ingest_module, "ingest", fake)
    result = CliRunner().invoke(
        app, ["ingest", "--symbols", "fxa, fxe,nope", "--date", "2026-11-13", "--full"]
    )
    assert result.exit_code == 0, result.output
    assert seen == {"symbols": ["FXA", "FXE", "NOPE"], "as_of": date(2026, 11, 13), "full": True}
    assert "ingest 2026-11-13 provider=fixture" in result.output
    assert "daily=756" in result.output
    assert "split-refetch" in result.output
    assert "quality: degraded=1 ok=1" in result.output


def test_unit_cli_ingest_provider_outage_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: Any, **_k: Any) -> IngestSummary:
        raise IngestError("all tickers failed", code="provider_unavailable")

    monkeypatch.setattr(ingest_module, "ingest", boom)
    result = CliRunner().invoke(app, ["ingest", "--symbols", "FXA"])
    assert result.exit_code == 1
    assert "provider_unavailable" in result.output


def test_unit_cli_ingest_unreachable_database_exits_3(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: Any, **_k: Any) -> IngestSummary:
        raise OperationalError("SELECT 1", {}, Exception("password=hunter2"))

    monkeypatch.setattr(ingest_module, "ingest", boom)
    result = CliRunner().invoke(app, ["ingest", "--symbols", "FXA"])
    assert result.exit_code == 3
    assert "hunter2" not in result.output
