# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Initial schema: live tables (ARCHITECTURE 5.1) and the backtests schema (5.2, ADR-029).

Revision ID: 0001
Revises: none

Triggers are added by 0002 (section 5.3).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS backtests")
    op.create_table(
        "config_versions",
        sa.Column("hash", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "hash ~ '^sha256:[0-9a-f]{64}$'", name=op.f("ck_config_versions_hash_format")
        ),
        sa.PrimaryKeyConstraint("hash", name=op.f("pk_config_versions")),
    )
    op.create_table(
        "metric_counters",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "labels",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("value", sa.Float(), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("name", "labels", name=op.f("pk_metric_counters")),
    )
    op.create_table(
        "tickers",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), server_default="stock", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_benchmark", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("resolution", sa.Text(), server_default="resolved", nullable=False),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("avg_dollar_volume_20d", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "resolution IN ('resolved', 'unresolved', 'needs_review')",
            name=op.f("ck_tickers_resolution"),
        ),
        sa.CheckConstraint(
            "symbol ~ '^[A-Z][A-Z0-9.\\-]{0,9}$'", name=op.f("ck_tickers_symbol_format")
        ),
        sa.CheckConstraint(
            "type IN ('stock', 'etf', 'index', 'crypto')", name=op.f("ck_tickers_type")
        ),
        sa.PrimaryKeyConstraint("symbol", name=op.f("pk_tickers")),
    )
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), server_default="default", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watchlists")),
        sa.UniqueConstraint("name", name=op.f("uq_watchlists_name")),
    )
    op.create_index(
        "ux_watchlists_one_default",
        "watchlists",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("from_date", sa.Date(), nullable=False),
        sa.Column("to_date", sa.Date(), nullable=False),
        sa.Column("config_hash", sa.Text(), nullable=False),
        sa.Column("code_version", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tickers", sa.Integer(), nullable=False),
        sa.Column(
            "summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "state IN ('running', 'completed', 'failed')", name=op.f("ck_backtest_runs_state")
        ),
        sa.CheckConstraint("length(id) = 26", name=op.f("ck_backtest_runs_id_ulid")),
        sa.ForeignKeyConstraint(
            ["config_hash"],
            ["config_versions.hash"],
            name=op.f("fk_backtest_runs_config_hash_config_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_backtest_runs")),
        schema="backtests",
    )
    op.create_table(
        "bars_daily",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("vwap", sa.Float(), nullable=True),
        sa.Column(
            "adjusted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.CheckConstraint("high >= low", name=op.f("ck_bars_daily_high_ge_low")),
        sa.CheckConstraint("volume >= 0", name=op.f("ck_bars_daily_volume_non_negative")),
        sa.ForeignKeyConstraint(
            ["symbol"], ["tickers.symbol"], name=op.f("fk_bars_daily_symbol_tickers")
        ),
        sa.PrimaryKeyConstraint("symbol", "date", name=op.f("pk_bars_daily")),
    )
    op.create_index("ix_bars_daily_date", "bars_daily", ["date"], unique=False)
    op.create_table(
        "bars_intraday",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["symbol"], ["tickers.symbol"], name=op.f("fk_bars_intraday_symbol_tickers")
        ),
        sa.PrimaryKeyConstraint("symbol", "ts", name=op.f("pk_bars_intraday")),
    )
    op.create_index("ix_bars_intraday_ts", "bars_intraday", ["ts"], unique=False)
    op.create_table(
        "corporate_actions",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("ratio", sa.Float(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('split', 'dividend')", name=op.f("ck_corporate_actions_kind")),
        sa.ForeignKeyConstraint(
            ["symbol"], ["tickers.symbol"], name=op.f("fk_corporate_actions_symbol_tickers")
        ),
        sa.PrimaryKeyConstraint("symbol", "ex_date", "kind", name=op.f("pk_corporate_actions")),
    )
    op.create_table(
        "earnings_calendar",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "known_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["symbol"], ["tickers.symbol"], name=op.f("fk_earnings_calendar_symbol_tickers")
        ),
        sa.PrimaryKeyConstraint("symbol", "date", name=op.f("pk_earnings_calendar")),
    )
    op.create_table(
        "fundamentals",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["symbol"], ["tickers.symbol"], name=op.f("fk_fundamentals_symbol_tickers")
        ),
        sa.PrimaryKeyConstraint("symbol", "period_end", "known_at", name=op.f("pk_fundamentals")),
    )
    op.create_index(
        "ix_fundamentals_symbol_known_at", "fundamentals", ["symbol", "known_at"], unique=False
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("state", sa.Text(), server_default="queued", nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("config_hash", sa.Text(), nullable=False),
        sa.Column("code_version", sa.Text(), nullable=False),
        sa.Column("market_regime", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(state = 'published') = (published_at IS NOT NULL)", name=op.f("ck_runs_published")
        ),
        sa.CheckConstraint(
            (
                "state IN ('queued', 'ingesting', 'computing', 'scoring', 'selecting', "
                "'narrating', 'published', 'failed')"
            ),
            name=op.f("ck_runs_state"),
        ),
        sa.CheckConstraint(
            "trigger IN ('schedule', 'api', 'mcp', 'cli', 'demo')", name=op.f("ck_runs_trigger")
        ),
        sa.CheckConstraint("length(id) = 26", name=op.f("ck_runs_id_ulid")),
        sa.ForeignKeyConstraint(
            ["config_hash"],
            ["config_versions.hash"],
            name=op.f("fk_runs_config_hash_config_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by"], ["runs.id"], name=op.f("fk_runs_superseded_by_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
    )
    op.create_index(
        "ix_runs_trade_date_published_at", "runs", ["trade_date", "published_at"], unique=False
    )
    op.create_index(
        "ux_runs_one_active",
        "runs",
        [sa.literal_column("(1)")],
        unique=True,
        postgresql_where=sa.text("state NOT IN ('published', 'failed')"),
    )
    op.create_index(
        "ux_runs_one_current_per_date",
        "runs",
        ["trade_date"],
        unique=True,
        postgresql_where=sa.text("published_at IS NOT NULL AND superseded_by IS NULL"),
    )
    op.create_table(
        "watchlist_groups",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("watchlist_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9][a-z0-9-]{0,47}$'", name=op.f("ck_watchlist_groups_slug_format")
        ),
        sa.CheckConstraint("char_length(name) <= 64", name=op.f("ck_watchlist_groups_name_length")),
        sa.ForeignKeyConstraint(
            ["watchlist_id"],
            ["watchlists.id"],
            name=op.f("fk_watchlist_groups_watchlist_id_watchlists"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watchlist_groups")),
        sa.UniqueConstraint(
            "watchlist_id", "slug", name=op.f("uq_watchlist_groups_watchlist_id_slug")
        ),
    )
    op.create_table(
        "watchlist_items",
        sa.Column("watchlist_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("source", sa.Text(), server_default="user", nullable=False),
        sa.Column("scored", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(
            "source IN ('seed', 'user', 'api', 'cli', 'mcp')",
            name=op.f("ck_watchlist_items_source"),
        ),
        sa.ForeignKeyConstraint(
            ["symbol"], ["tickers.symbol"], name=op.f("fk_watchlist_items_symbol_tickers")
        ),
        sa.ForeignKeyConstraint(
            ["watchlist_id"],
            ["watchlists.id"],
            name=op.f("fk_watchlist_items_watchlist_id_watchlists"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("watchlist_id", "symbol", name=op.f("pk_watchlist_items")),
    )
    op.create_table(
        "equity_curve",
        sa.Column("backtest_id", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("strategy_equity", sa.Float(), nullable=False),
        sa.Column("benchmark_equity", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["backtest_id"],
            ["backtests.backtest_runs.id"],
            name=op.f("fk_equity_curve_backtest_id_backtest_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("backtest_id", "date", name=op.f("pk_equity_curve")),
        schema="backtests",
    )
    op.create_table(
        "picks",
        sa.Column("backtest_id", sa.Text(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("display_score", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("band", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["backtest_id"],
            ["backtests.backtest_runs.id"],
            name=op.f("fk_picks_backtest_id_backtest_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("backtest_id", "trade_date", "side", "rank", name=op.f("pk_picks")),
        schema="backtests",
    )
    op.create_table(
        "indicator_snapshots",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_indicator_snapshots_run_id_runs")
        ),
        sa.ForeignKeyConstraint(
            ["symbol"], ["tickers.symbol"], name=op.f("fk_indicator_snapshots_symbol_tickers")
        ),
        sa.PrimaryKeyConstraint("run_id", "symbol", name=op.f("pk_indicator_snapshots")),
    )
    op.create_table(
        "provider_calls",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_provider_calls_run_id_runs"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_calls")),
    )
    op.create_index(
        "ix_provider_calls_provider_ts", "provider_calls", ["provider", "ts"], unique=False
    )
    op.create_index("ix_provider_calls_ts", "provider_calls", ["ts"], unique=False)
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("display_score", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("band", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("side IN ('buy', 'sell')", name=op.f("ck_recommendations_side")),
        sa.CheckConstraint("length(id) = 26", name=op.f("ck_recommendations_id_ulid")),
        sa.CheckConstraint("rank >= 1", name=op.f("ck_recommendations_rank")),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_recommendations_run_id_runs")
        ),
        sa.ForeignKeyConstraint(
            ["symbol"], ["tickers.symbol"], name=op.f("fk_recommendations_symbol_tickers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendations")),
        sa.UniqueConstraint("run_id", "side", "rank", name="ix_recommendations_run_side_rank"),
        sa.UniqueConstraint("run_id", "symbol", name=op.f("uq_recommendations_run_id_symbol")),
    )
    op.create_index(
        "ix_recommendations_symbol_trade_date",
        "recommendations",
        ["symbol", "trade_date"],
        unique=False,
    )
    op.create_table(
        "run_transitions",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.Text(), nullable=True),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_run_transitions_run_id_runs")
        ),
        sa.PrimaryKeyConstraint("run_id", "seq", name=op.f("pk_run_transitions")),
    )
    op.create_table(
        "ticker_scores",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
        sa.Column("data_quality", sa.Text(), nullable=False),
        sa.Column("composite", sa.Float(), nullable=True),
        sa.Column("display_score", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("band", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("regime", sa.Text(), nullable=True),
        sa.Column("st_dir_d", sa.SmallInteger(), nullable=True),
        sa.Column("st_dir_w", sa.SmallInteger(), nullable=True),
        sa.Column("bars_since_flip", sa.Integer(), nullable=True),
        sa.Column("st_line", sa.Float(), nullable=True),
        sa.Column("buy_threshold", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("sell_threshold", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("candidate", sa.Text(), nullable=True),
        sa.Column("rank_overall", sa.Integer(), nullable=True),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "adjustments",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "flags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("avg_dollar_volume_20d", sa.Float(), nullable=True),
        sa.Column("rel_volume", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "status = 'scored' OR exclusion_reason IS NOT NULL",
            name=op.f("ck_ticker_scores_exclusion"),
        ),
        sa.CheckConstraint(
            "status IN ('scored', 'excluded')", name=op.f("ck_ticker_scores_status")
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_ticker_scores_run_id_runs")),
        sa.ForeignKeyConstraint(
            ["symbol"], ["tickers.symbol"], name=op.f("fk_ticker_scores_symbol_tickers")
        ),
        sa.PrimaryKeyConstraint("run_id", "symbol", name=op.f("pk_ticker_scores")),
    )
    op.create_index(
        "ix_ticker_scores_symbol_run", "ticker_scores", ["symbol", "run_id"], unique=False
    )
    op.create_table(
        "watchlist_group_members",
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("watchlist_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["watchlist_groups.id"],
            name=op.f("fk_watchlist_group_members_group_id_watchlist_groups"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["watchlist_id", "symbol"],
            ["watchlist_items.watchlist_id", "watchlist_items.symbol"],
            name=op.f("fk_watchlist_group_members_watchlist_id_symbol_watchlist_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("group_id", "symbol", name=op.f("pk_watchlist_group_members")),
    )
    op.create_index(
        "ix_watchlist_group_members_item",
        "watchlist_group_members",
        ["watchlist_id", "symbol"],
        unique=False,
    )
    op.create_table(
        "outcomes",
        sa.Column("backtest_id", sa.Text(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("horizon_days", sa.SmallInteger(), nullable=False),
        sa.Column("pick_return", sa.Float(), nullable=False),
        sa.Column("benchmark_return", sa.Float(), nullable=False),
        sa.Column("excess_return", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["backtest_id", "trade_date", "side", "rank"],
            [
                "backtests.picks.backtest_id",
                "backtests.picks.trade_date",
                "backtests.picks.side",
                "backtests.picks.rank",
            ],
            name=op.f("fk_outcomes_backtest_id_trade_date_side_rank_picks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "backtest_id", "trade_date", "side", "rank", "horizon_days", name=op.f("pk_outcomes")
        ),
        schema="backtests",
    )
    op.create_table(
        "factor_scores",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("factor_id", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("contribution", sa.Float(), nullable=False),
        sa.Column("quality", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("score BETWEEN -100 AND 100", name=op.f("ck_factor_scores_score_range")),
        sa.ForeignKeyConstraint(
            ["run_id", "symbol"],
            ["ticker_scores.run_id", "ticker_scores.symbol"],
            name=op.f("fk_factor_scores_run_id_symbol_ticker_scores"),
        ),
        sa.PrimaryKeyConstraint("run_id", "symbol", "factor_id", name=op.f("pk_factor_scores")),
    )
    op.create_index(
        "ix_factor_scores_symbol_run", "factor_scores", ["symbol", "run_id"], unique=False
    )
    op.create_table(
        "narratives",
        sa.Column("recommendation_id", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column(
            "rejection_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint("source IN ('llm', 'template')", name=op.f("ck_narratives_source")),
        sa.CheckConstraint("char_length(text) <= 1200", name=op.f("ck_narratives_text_length")),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["recommendations.id"],
            name=op.f("fk_narratives_recommendation_id_recommendations"),
        ),
        sa.PrimaryKeyConstraint("recommendation_id", name=op.f("pk_narratives")),
    )
    op.create_table(
        "outcomes",
        sa.Column("recommendation_id", sa.Text(), nullable=False),
        sa.Column("horizon_days", sa.SmallInteger(), nullable=False),
        sa.Column("exit_date", sa.Date(), nullable=False),
        sa.Column("pick_return", sa.Float(), nullable=False),
        sa.Column("benchmark_return", sa.Float(), nullable=False),
        sa.Column("excess_return", sa.Float(), nullable=False),
        sa.Column("adjustment_factor", sa.Float(), server_default="1.0", nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("horizon_days IN (1, 5, 10, 20)", name=op.f("ck_outcomes_horizon")),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["recommendations.id"],
            name=op.f("fk_outcomes_recommendation_id_recommendations"),
        ),
        sa.PrimaryKeyConstraint("recommendation_id", "horizon_days", name=op.f("pk_outcomes")),
    )


def downgrade() -> None:
    op.drop_table("outcomes")
    op.drop_table("narratives")
    op.drop_index("ix_factor_scores_symbol_run", table_name="factor_scores")
    op.drop_table("factor_scores")
    op.drop_table("outcomes", schema="backtests")
    op.drop_index("ix_watchlist_group_members_item", table_name="watchlist_group_members")
    op.drop_table("watchlist_group_members")
    op.drop_index("ix_ticker_scores_symbol_run", table_name="ticker_scores")
    op.drop_table("ticker_scores")
    op.drop_table("run_transitions")
    op.drop_index("ix_recommendations_symbol_trade_date", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index("ix_provider_calls_ts", table_name="provider_calls")
    op.drop_index("ix_provider_calls_provider_ts", table_name="provider_calls")
    op.drop_table("provider_calls")
    op.drop_table("indicator_snapshots")
    op.drop_table("picks", schema="backtests")
    op.drop_table("equity_curve", schema="backtests")
    op.drop_table("watchlist_items")
    op.drop_table("watchlist_groups")
    op.drop_index(
        "ux_runs_one_current_per_date",
        table_name="runs",
        postgresql_where=sa.text("published_at IS NOT NULL AND superseded_by IS NULL"),
    )
    op.drop_index(
        "ux_runs_one_active",
        table_name="runs",
        postgresql_where=sa.text("state NOT IN ('published', 'failed')"),
    )
    op.drop_index("ix_runs_trade_date_published_at", table_name="runs")
    op.drop_table("runs")
    op.drop_index("ix_fundamentals_symbol_known_at", table_name="fundamentals")
    op.drop_table("fundamentals")
    op.drop_table("earnings_calendar")
    op.drop_table("corporate_actions")
    op.drop_index("ix_bars_intraday_ts", table_name="bars_intraday")
    op.drop_table("bars_intraday")
    op.drop_index("ix_bars_daily_date", table_name="bars_daily")
    op.drop_table("bars_daily")
    op.drop_table("backtest_runs", schema="backtests")
    op.drop_index(
        "ux_watchlists_one_default", table_name="watchlists", postgresql_where=sa.text("is_default")
    )
    op.drop_table("watchlists")
    op.drop_table("tickers")
    op.drop_table("metric_counters")
    op.drop_table("config_versions")
    op.execute("DROP SCHEMA IF EXISTS backtests")
