# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""`supertrends db migrate` (ARCHITECTURE section 6.2, 5.4)."""

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError
from typer.testing import CliRunner

from supertrends.cli.main import app
from supertrends.data import db


def test_unit_cli_db_migrate_prints_applied_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_migrate(engine: Engine, revision: str = "head") -> str:
        calls.append(revision)
        return "0002"

    monkeypatch.setenv("SUPERTRENDS_DATABASE_URL", "sqlite://")
    monkeypatch.setattr(db, "migrate", fake_migrate)
    result = CliRunner().invoke(app, ["db", "migrate"])
    assert result.exit_code == 0
    assert result.output.strip() == "revision 0002"
    assert calls == ["head"]


def test_unit_cli_db_migrate_passes_revision_option(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    monkeypatch.setenv("SUPERTRENDS_DATABASE_URL", "sqlite://")
    monkeypatch.setattr(db, "migrate", lambda _e, revision="head": seen.append(revision) or "0001")
    result = CliRunner().invoke(app, ["db", "migrate", "--revision", "0001"])
    assert result.exit_code == 0
    assert seen == ["0001"]


def test_unit_cli_db_migrate_unreachable_database_exits_3(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_e: Engine, revision: str = "head") -> str:
        raise OperationalError("SELECT 1", {}, Exception("password=hunter2"))

    monkeypatch.setenv("SUPERTRENDS_DATABASE_URL", "sqlite://")
    monkeypatch.setattr(db, "migrate", boom)
    result = CliRunner().invoke(app, ["db", "migrate"])
    assert result.exit_code == 3
    assert "hunter2" not in result.output
