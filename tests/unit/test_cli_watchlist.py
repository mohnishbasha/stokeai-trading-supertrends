# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""`supertrends watchlist` commands and the seed-on-start hook (SQLite stand-in)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError
from typer.testing import CliRunner

from supertrends.cli import main as cli
from supertrends.data import db
from supertrends.data import watchlist as wl


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, watchlist_url: str, watchlist_engine: Engine) -> None:
    monkeypatch.setenv("SUPERTRENDS_DATABASE_URL", watchlist_url)
    db.reset_engine()


def _run(*args: str) -> tuple[int, str]:
    result = CliRunner().invoke(cli.app, ["watchlist", *args])
    return result.exit_code, result.output


@pytest.mark.usefixtures("env")
def test_unit_cli_watchlist_seed_list_add_remove_round_trip() -> None:
    code, out = _run("seed")
    assert code == 0
    assert "14 groups and 199 symbols" in out
    assert _run("seed")[1].startswith("watchlist already exists")
    code, out = _run("list")
    assert code == 0
    assert "watchlist default: 199 of 300 tickers" in out
    assert "CITI: needs_review" in out
    code, out = _run("list", "--json")
    assert json.loads(out)["count"] == 199
    assert _run("add", "zzco", "--group", "fab-7") == (0, "added ZZCO\n")
    code, out = _run("add", "zzco")
    assert code == 2
    assert "already" in out
    assert _run("remove", "zzco") == (0, "removed ZZCO\n")
    assert _run("remove", "ZZCO")[0] == 2


@pytest.mark.usefixtures("env")
def test_unit_cli_watchlist_unreachable_database_exits_3(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("password=hunter2"))

    monkeypatch.setattr(wl, "read_watchlist", boom)
    code, out = _run("list")
    assert code == 3
    assert "hunter2" not in out


def test_unit_cli_serve_seeds_first_start_and_survives_database_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uvicorn = MagicMock()
    monkeypatch.setitem(__import__("sys").modules, "uvicorn", uvicorn)
    seen = iter(
        [wl.SeedResult(groups=14, symbols=199), None, OperationalError("x", {}, Exception())]
    )

    def fake(_resolver: object) -> wl.SeedResult | None:
        value = next(seen)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(wl, "seed_if_empty", fake)
    for _ in range(3):
        assert CliRunner().invoke(cli.app, ["serve"]).exit_code == 0
    assert uvicorn.run.call_count == 3
