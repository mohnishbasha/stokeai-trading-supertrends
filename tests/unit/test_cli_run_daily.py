# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""`supertrends run daily` output and exit codes (TS-CLI-010, TS-OPS-109 to 112; S3-T07).

The orchestrator is faked; the real pipeline runs in tests/integration/test_runs.py.
"""

from __future__ import annotations

import json
import signal
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.exc import OperationalError
from typer.testing import CliRunner

from supertrends.cli.main import app
from supertrends.runs import orchestrator, service
from supertrends.runs.narrator import DISCLAIMER
from supertrends.runs.orchestrator import RunOutcome
from supertrends.runs.state import RunState

DAY = date(2026, 11, 13)
RUN_ID = "01JA0000000000000000000001"
SUMMARY = {
    "tickers_scored": 10,
    "tickers_excluded": 2,
    "excluded": [
        {"ticker": "FXK", "reason": "stale"},
        {"ticker": "FXJ", "reason": "insufficient_history"},
    ],
}


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERTRENDS_DATABASE_URL", "postgresql://u:p@127.0.0.1:1/none")
    monkeypatch.setenv("SUPERTRENDS_MARKET_PROVIDER", "fixture")
    monkeypatch.setenv("SUPERTRENDS_FUNDAMENTALS_PROVIDER", "fixture")
    monkeypatch.setenv("SUPERTRENDS_FIXTURE_END_DATE", "2026-11-13")


def _fake_run(monkeypatch: pytest.MonkeyPatch, outcome: RunOutcome) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def fake(_engine: Any, deps: Any, **kwargs: Any) -> RunOutcome:
        seen.update(kwargs, deps=deps)
        progress = kwargs["progress"]
        if outcome.run_id:
            for state in (RunState.QUEUED, RunState.INGESTING, RunState.PUBLISHED):
                progress(outcome.run_id, state)
        return outcome

    picks = [
        SimpleNamespace(
            side="buy",
            rank=1,
            symbol="FXL",
            display_score=69.7,
            confidence=71.0,
            band="buy",
            disclaimer=DISCLAIMER,
        )
    ]
    monkeypatch.setattr(orchestrator, "execute_run", fake)
    monkeypatch.setattr(service, "recommendations_for_run", lambda _e, _r: picks)
    return seen


def test_unit_cli_run_daily_date_flag_runs_that_date(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _fake_run(monkeypatch, RunOutcome("published", DAY, run_id=RUN_ID, summary=SUMMARY))
    result = CliRunner().invoke(app, ["run", "daily", "--date", "2026-11-13"])
    assert result.exit_code == 0, result.output
    assert seen["trade_date"] == DAY
    assert seen["trigger"] == "cli"
    assert seen["deps"].queued_timeout_seconds == 600
    lines = result.output.splitlines()
    assert lines[:3] == [f"{RUN_ID} queued", f"{RUN_ID} ingesting", f"{RUN_ID} published"]
    assert f"published {RUN_ID} for 2026-11-13: scored 10, excluded 2" in lines
    assert "excluded FXK: stale" in lines
    assert "excluded FXJ: insufficient_history" in lines
    assert any(line.startswith("BUY  1 FXL") for line in lines)
    assert lines[-1] == DISCLAIMER


def test_unit_cli_run_daily_json_includes_picks_with_disclaimer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_run(monkeypatch, RunOutcome("published", DAY, run_id=RUN_ID, summary=SUMMARY))
    result = CliRunner().invoke(app, ["run", "daily", "--date", "2026-11-13", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "published"
    assert payload["trade_date"] == "2026-11-13"
    assert payload["summary"]["excluded"][0] == {"ticker": "FXK", "reason": "stale"}
    assert payload["picks"][0]["ticker"] == "FXL"
    assert payload["picks"][0]["disclaimer"] == DISCLAIMER


def test_unit_cli_run_daily_failed_run_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_run(
        monkeypatch,
        RunOutcome(
            "failed",
            DAY,
            run_id=RUN_ID,
            error_code="benchmark_unavailable",
            error_detail="benchmark data unavailable: SPY",
        ),
    )
    result = CliRunner().invoke(app, ["run", "daily", "--date", "2026-11-13"])
    assert result.exit_code == 1
    assert "failed" in result.output
    assert "benchmark_unavailable" in result.output


def test_unit_cli_run_daily_already_running_same_date_exits_0_other_date_exits_3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_run(
        monkeypatch,
        RunOutcome("already_running", DAY, active_run_id=RUN_ID, active_trade_date=DAY),
    )
    same = CliRunner().invoke(app, ["run", "daily", "--date", "2026-11-13"])
    assert same.exit_code == 0, same.output
    assert "already running for 2026-11-13" in same.output
    _fake_run(monkeypatch, RunOutcome("already_running", DAY))
    unknown = CliRunner().invoke(app, ["run", "daily", "--date", "2026-11-13"])
    assert unknown.exit_code == 0
    _fake_run(
        monkeypatch,
        RunOutcome(
            "already_running", DAY, active_run_id=RUN_ID, active_trade_date=date(2026, 11, 12)
        ),
    )
    other = CliRunner().invoke(app, ["run", "daily", "--date", "2026-11-13"])
    assert other.exit_code == 3
    assert "another run is active for 2026-11-12" in other.output
    as_json = CliRunner().invoke(app, ["run", "daily", "--date", "2026-11-13", "--json"])
    assert as_json.exit_code == 3
    assert json.loads(as_json.output)["active_trade_date"] == "2026-11-12"


def test_unit_cli_run_daily_invalid_dates_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_run(monkeypatch, RunOutcome("published", DAY, run_id=RUN_ID))
    bad = CliRunner().invoke(app, ["run", "daily", "--date", "tomorrow"])
    assert bad.exit_code == 2
    assert "invalid --date" in bad.output
    holiday = CliRunner().invoke(app, ["run", "daily", "--date", "2025-12-25"])
    assert holiday.exit_code == 2
    assert "not_a_trading_date" in holiday.output
    future = CliRunner().invoke(app, ["run", "daily", "--date", "2099-01-02"])
    assert future.exit_code == 2
    assert "date_in_future" in future.output


def test_unit_cli_run_daily_database_error_exits_3_and_sigterm_exits_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*_a: Any, **_k: Any) -> RunOutcome:
        raise OperationalError("select 1", {}, Exception("refused"))

    monkeypatch.setattr(orchestrator, "execute_run", broken)
    result = CliRunner().invoke(app, ["run", "daily", "--date", "2026-11-13"])
    assert result.exit_code == 3
    assert "database error" in result.output

    def terminated(*_a: Any, **_k: Any) -> RunOutcome:
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler)
        handler(signal.SIGTERM, None)
        raise AssertionError("unreachable")  # pragma: no cover

    before = signal.getsignal(signal.SIGTERM)
    monkeypatch.setattr(orchestrator, "execute_run", terminated)
    result = CliRunner().invoke(app, ["run", "daily", "--date", "2026-11-13"])
    assert result.exit_code == 1
    assert "run terminated" in result.output
    assert signal.getsignal(signal.SIGTERM) == before


def test_unit_cli_run_daily_published_without_picks_still_prints_disclaimer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_run(monkeypatch, RunOutcome("published", DAY, run_id=RUN_ID, summary={}))
    monkeypatch.setattr(service, "recommendations_for_run", lambda _e, _r: [])
    result = CliRunner().invoke(app, ["run", "daily", "--date", "2026-11-13"])
    assert result.exit_code == 0
    assert "no picks today" in result.output
    assert result.output.splitlines()[-1] == DISCLAIMER
