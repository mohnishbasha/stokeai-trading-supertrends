# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Scheduled daily run: the market-closed exit and `make run-daily` (TS-OPS-011, 131 to 140; S3-T10).

A fake clock stands in for the CronJob firing at 17:30 New York on a holiday. The database is
never touched, so the same scenario against real Postgres lives in tests/integration.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from supertrends.cli.main import app
from supertrends.data import db
from supertrends.runs import dates, orchestrator
from supertrends.runs.dates import MARKET_CLOSED, TradeDateError, resolve_trade_date

ROOT = Path(__file__).resolve().parents[2]
THANKSGIVING_CRON = datetime(2026, 11, 26, 22, 30, tzinfo=UTC)  # 17:30 New York
SATURDAY_CRON = datetime(2026, 11, 14, 22, 30, tzinfo=UTC)
FRIDAY_CRON = datetime(2026, 11, 13, 22, 30, tzinfo=UTC)


@pytest.fixture
def holiday_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dates, "utc_now", lambda: THANKSGIVING_CRON)
    monkeypatch.setenv("SUPERTRENDS_DATABASE_URL", "postgresql://u:p@127.0.0.1:1/none")


@pytest.fixture
def no_database(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"engine": 0, "run": 0}

    def engine(*_a: Any, **_k: Any) -> None:
        calls["engine"] += 1
        raise AssertionError("market closed must not open the database")

    def run(*_a: Any, **_k: Any) -> None:
        calls["run"] += 1
        raise AssertionError("market closed must not execute a run")

    monkeypatch.setattr(db, "create_db_engine", engine)
    monkeypatch.setattr(orchestrator, "execute_run", run)
    return calls


def test_unit_runs_daily_non_trading_day_exits_0_publishes_nothing(
    holiday_clock: None, no_database: dict[str, int]
) -> None:
    result = CliRunner().invoke(app, ["run", "daily"])
    assert result.exit_code == 0, result.output
    assert "market closed" in result.output
    assert no_database == {"engine": 0, "run": 0}


def test_unit_runs_trade_date_without_date_on_holiday_is_market_closed_exit_0() -> None:
    with pytest.raises(TradeDateError) as holiday:
        resolve_trade_date(None, THANKSGIVING_CRON)
    assert holiday.value.code == MARKET_CLOSED
    assert holiday.value.exit_code == 0
    assert "2026-11-26" in str(holiday.value)


def test_unit_runs_trade_date_without_date_on_weekend_is_market_closed_exit_0() -> None:
    with pytest.raises(TradeDateError) as weekend:
        resolve_trade_date(None, SATURDAY_CRON)
    assert weekend.value.code == MARKET_CLOSED
    assert weekend.value.exit_code == 0


def test_unit_runs_trade_date_clock_defaults_to_utc_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dates, "utc_now", lambda: FRIDAY_CRON)
    assert resolve_trade_date(None) == date(2026, 11, 13)


def test_unit_runs_daily_market_closed_json_reports_no_run(
    holiday_clock: None, no_database: dict[str, int]
) -> None:
    result = CliRunner().invoke(app, ["run", "daily", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload == {"status": "market_closed", "trade_date": "2026-11-26", "run_id": None}
    assert no_database["engine"] == 0


def test_unit_runs_daily_explicit_holiday_date_still_exits_2(
    holiday_clock: None, no_database: dict[str, int]
) -> None:
    result = CliRunner().invoke(app, ["run", "daily", "--date", "2025-12-25"])
    assert result.exit_code == 2
    assert "not_a_trading_date" in result.output
    assert no_database == {"engine": 0, "run": 0}


def test_unit_runs_daily_before_close_still_exits_3_not_market_closed(
    monkeypatch: pytest.MonkeyPatch, no_database: dict[str, int]
) -> None:
    monkeypatch.setenv("SUPERTRENDS_DATABASE_URL", "postgresql://u:p@127.0.0.1:1/none")
    monkeypatch.setattr(dates, "utc_now", lambda: datetime(2026, 11, 13, 15, 0, tzinfo=UTC))
    result = CliRunner().invoke(app, ["run", "daily"])
    assert result.exit_code == 3
    assert "session_not_complete" in result.output


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
def test_unit_runs_make_run_daily_calls_the_cli_locally_or_in_compose() -> None:
    local = subprocess.run(  # noqa: S603
        ["make", "-n", "run-daily"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "SUPERTRENDS_DATABASE_URL": "postgresql://x"},
    ).stdout
    assert "supertrends run daily" in local
    assert "docker compose" not in local
    compose = subprocess.run(  # noqa: S603
        ["make", "-n", "run-daily"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin"},
    ).stdout
    assert "docker compose -f deploy/compose/docker-compose.local.yml run --rm app run daily" in (
        compose
    )


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
def test_unit_runs_make_run_daily_passes_date() -> None:
    out = subprocess.run(  # noqa: S603
        ["make", "-n", "run-daily", "DATE=2026-11-13"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "SUPERTRENDS_DATABASE_URL": "postgresql://x"},
    ).stdout
    assert "--date 2026-11-13" in out
