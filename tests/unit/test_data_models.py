# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Model metadata matches ARCHITECTURE section 5 (no database needed)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa

from supertrends.data import models
from supertrends.data.models import Base

LIVE_TABLES = {
    "tickers",
    "watchlists",
    "watchlist_items",
    "watchlist_groups",
    "watchlist_group_members",
    "bars_daily",
    "bars_intraday",
    "corporate_actions",
    "fundamentals",
    "earnings_calendar",
    "config_versions",
    "runs",
    "run_transitions",
    "indicator_snapshots",
    "ticker_scores",
    "factor_scores",
    "recommendations",
    "narratives",
    "outcomes",
    "provider_calls",
    "metric_counters",
}
BACKTEST_TABLES = {
    "backtests.backtest_runs",
    "backtests.picks",
    "backtests.outcomes",
    "backtests.equity_curve",
}
VERSIONS = Path(__file__).resolve().parents[2] / "migrations" / "versions"


def _table(name: str) -> sa.Table:
    return Base.metadata.tables[name]


def _pk(name: str) -> list[str]:
    return [c.name for c in _table(name).primary_key.columns]


def test_unit_models_define_every_live_and_backtest_table() -> None:
    assert set(Base.metadata.tables) == LIVE_TABLES | BACKTEST_TABLES


def test_unit_models_bars_have_composite_primary_keys_on_symbol_and_time() -> None:
    assert _pk("bars_daily") == ["symbol", "date"]
    assert _pk("bars_intraday") == ["symbol", "ts"]


@pytest.mark.parametrize(
    ("table", "expected"),
    [
        ("tickers", ["symbol"]),
        ("watchlist_items", ["watchlist_id", "symbol"]),
        ("watchlist_group_members", ["group_id", "symbol"]),
        ("corporate_actions", ["symbol", "ex_date", "kind"]),
        ("fundamentals", ["symbol", "period_end", "known_at"]),
        ("earnings_calendar", ["symbol", "date"]),
        ("config_versions", ["hash"]),
        ("runs", ["id"]),
        ("run_transitions", ["run_id", "seq"]),
        ("indicator_snapshots", ["run_id", "symbol"]),
        ("ticker_scores", ["run_id", "symbol"]),
        ("factor_scores", ["run_id", "symbol", "factor_id"]),
        ("recommendations", ["id"]),
        ("narratives", ["recommendation_id"]),
        ("outcomes", ["recommendation_id", "horizon_days"]),
        ("provider_calls", ["id"]),
        ("metric_counters", ["name", "labels"]),
        ("backtests.picks", ["backtest_id", "trade_date", "side", "rank"]),
        ("backtests.equity_curve", ["backtest_id", "date"]),
    ],
)
def test_unit_models_primary_keys_match_spec(table: str, expected: list[str]) -> None:
    assert _pk(table) == expected


def test_unit_models_outcomes_uses_pick_return_not_return() -> None:
    assert "pick_return" in _table("outcomes").c
    assert "return" not in _table("outcomes").c


def test_unit_models_watchlist_items_has_no_group_name_column() -> None:
    assert "group_name" not in _table("watchlist_items").c


def test_unit_models_factor_scores_foreign_key_targets_ticker_scores() -> None:
    fks = {fk.referred_table.name for fk in _table("factor_scores").foreign_key_constraints}
    assert fks == {"ticker_scores"}


def test_unit_models_runs_has_partial_unique_indexes() -> None:
    indexes = {i.name: i for i in _table("runs").indexes}
    assert indexes["ux_runs_one_active"].unique
    assert indexes["ux_runs_one_current_per_date"].unique
    assert "ix_runs_trade_date_published_at" in indexes


def test_unit_models_recommendations_unique_run_side_rank_and_run_symbol() -> None:
    uniques = {
        tuple(c.name for c in u.columns)
        for u in _table("recommendations").constraints
        if isinstance(u, sa.UniqueConstraint)
    }
    assert ("run_id", "side", "rank") in uniques
    assert ("run_id", "symbol") in uniques


@pytest.mark.parametrize("table", ["runs", "recommendations", "backtests.backtest_runs"])
def test_unit_models_ulid_tables_check_id_length(table: str) -> None:
    checks = [
        str(c.sqltext) for c in _table(table).constraints if isinstance(c, sa.CheckConstraint)
    ]
    assert "length(id) = 26" in checks


def test_unit_models_every_constraint_is_named() -> None:
    for table in Base.metadata.tables.values():
        for constraint in table.constraints:
            assert constraint.name is not None, f"{table.name} has an unnamed constraint"


def test_unit_models_append_only_tables_exist_and_match_migration() -> None:
    spec = importlib.util.spec_from_file_location(
        "m0002", VERSIONS / "0002_append_only_triggers.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert tuple(module.APPEND_ONLY_TABLES) == models.APPEND_ONLY_TABLES
    assert module.WATCHLIST_CAP == models.WATCHLIST_ITEM_CAP
    assert set(models.APPEND_ONLY_TABLES) <= LIVE_TABLES


def test_unit_migrations_form_a_linear_chain_with_sequential_prefixes() -> None:
    files = sorted(p.name for p in VERSIONS.glob("*.py"))
    assert files
    for index, name in enumerate(files, start=1):
        assert name.startswith(f"{index:04d}_"), name
