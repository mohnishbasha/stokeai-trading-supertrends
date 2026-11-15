# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""SQLAlchemy 2 models for the complete live schema (ARCHITECTURE section 5.1, 5.2).

These models describe the schema; they never create it. Tables, triggers, and the `backtests`
schema are created by the Alembic revisions in `migrations/versions/` (section 5.4), and the
append-only triggers (section 5.3) live only in migrations. An integration test compares this
metadata against the migrated database so the two cannot drift.

Timestamps are `timestamptz` (UTC), prices are `double precision`, volumes are `bigint`, and
run, recommendation, and backtest IDs are 26-character ULIDs stored as `text`.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy import ForeignKeyConstraint, Index, MetaData
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

BACKTEST_SCHEMA = "backtests"
RUN_STATES = (
    "queued",
    "ingesting",
    "computing",
    "scoring",
    "selecting",
    "narrating",
    "published",
    "failed",
)
APPEND_ONLY_TABLES = (
    "config_versions",
    "run_transitions",
    "indicator_snapshots",
    "ticker_scores",
    "factor_scores",
    "narratives",
    "outcomes",
)
WATCHLIST_ITEM_CAP = 300

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

_NOW = sa.text("now()")
_EMPTY_OBJECT = sa.text("'{}'::jsonb")
_EMPTY_ARRAY = sa.text("'[]'::jsonb")
_TS = sa.DateTime(timezone=True)
_ULID = "length(id) = 26"


class Base(DeclarativeBase):
    """Declarative base with deterministic constraint names."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {  # noqa: RUF012 (SQLAlchemy declarative contract)
        dt.datetime: _TS,
    }


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Ticker(Base):
    """A tradable symbol (stock, ETF, index, crypto)."""

    __tablename__ = "tickers"
    __table_args__ = (
        sa.CheckConstraint(r"symbol ~ '^[A-Z][A-Z0-9.\-]{0,9}$'", name="symbol_format"),
        sa.CheckConstraint(_in("type", ("stock", "etf", "index", "crypto")), name="type"),
        sa.CheckConstraint(
            _in("resolution", ("resolved", "unresolved", "needs_review")), name="resolution"
        ),
    )

    symbol: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    name: Mapped[str | None] = mapped_column(sa.Text)
    type: Mapped[str] = mapped_column(sa.Text, server_default="stock")
    active: Mapped[bool] = mapped_column(server_default=sa.true())
    is_benchmark: Mapped[bool] = mapped_column(server_default=sa.false())
    resolution: Mapped[str] = mapped_column(sa.Text, server_default="resolved")
    resolution_reason: Mapped[str | None] = mapped_column(sa.Text)
    avg_dollar_volume_20d: Mapped[float | None] = mapped_column(sa.Float)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=_NOW)
    updated_at: Mapped[dt.datetime] = mapped_column(server_default=_NOW)


class Watchlist(Base):
    """A named watchlist; exactly one is the default."""

    __tablename__ = "watchlists"
    __table_args__ = (
        Index(
            "ux_watchlists_one_default",
            "is_default",
            unique=True,
            postgresql_where=sa.text("is_default"),
        ),
    )

    id: Mapped[int] = mapped_column(sa.Integer, sa.Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(sa.Text, unique=True, server_default="default")
    is_default: Mapped[bool] = mapped_column(server_default=sa.true())
    created_at: Mapped[dt.datetime] = mapped_column(server_default=_NOW)


class WatchlistItem(Base):
    """One row per (watchlist, symbol); group membership lives in watchlist_group_members."""

    __tablename__ = "watchlist_items"
    __table_args__ = (
        sa.CheckConstraint(_in("source", ("seed", "user", "api", "cli", "mcp")), name="source"),
    )

    watchlist_id: Mapped[int] = mapped_column(
        sa.ForeignKey("watchlists.id", ondelete="CASCADE"), primary_key=True
    )
    symbol: Mapped[str] = mapped_column(sa.ForeignKey("tickers.symbol"), primary_key=True)
    added_at: Mapped[dt.datetime] = mapped_column(server_default=_NOW)
    source: Mapped[str] = mapped_column(sa.Text, server_default="user")
    scored: Mapped[bool] = mapped_column(server_default=sa.true())


class WatchlistGroup(Base):
    """A display group inside a watchlist (ADR-019)."""

    __tablename__ = "watchlist_groups"
    __table_args__ = (
        sa.UniqueConstraint("watchlist_id", "slug"),
        sa.CheckConstraint(r"slug ~ '^[a-z0-9][a-z0-9-]{0,47}$'", name="slug_format"),
        sa.CheckConstraint("char_length(name) <= 64", name="name_length"),
    )

    id: Mapped[int] = mapped_column(sa.Integer, sa.Identity(), primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(sa.ForeignKey("watchlists.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(sa.Text)
    name: Mapped[str] = mapped_column(sa.Text)
    position: Mapped[int] = mapped_column(sa.Integer, server_default="0")


class WatchlistGroupMember(Base):
    """Links a group to a watchlist item (a symbol may sit in several groups)."""

    __tablename__ = "watchlist_group_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["watchlist_id", "symbol"],
            ["watchlist_items.watchlist_id", "watchlist_items.symbol"],
            ondelete="CASCADE",
        ),
        Index("ix_watchlist_group_members_item", "watchlist_id", "symbol"),
    )

    group_id: Mapped[int] = mapped_column(
        sa.ForeignKey("watchlist_groups.id", ondelete="CASCADE"), primary_key=True
    )
    watchlist_id: Mapped[int] = mapped_column(sa.Integer)
    symbol: Mapped[str] = mapped_column(sa.Text, primary_key=True)


class BarDaily(Base):
    """Daily OHLCV bar, adjusted per provider capability."""

    __tablename__ = "bars_daily"
    __table_args__ = (
        sa.CheckConstraint("volume >= 0", name="volume_non_negative"),
        sa.CheckConstraint("high >= low", name="high_ge_low"),
        Index("ix_bars_daily_date", "date"),
    )

    symbol: Mapped[str] = mapped_column(sa.ForeignKey("tickers.symbol"), primary_key=True)
    date: Mapped[dt.date] = mapped_column(sa.Date, primary_key=True)
    open: Mapped[float] = mapped_column(sa.Float)
    high: Mapped[float] = mapped_column(sa.Float)
    low: Mapped[float] = mapped_column(sa.Float)
    close: Mapped[float] = mapped_column(sa.Float)
    volume: Mapped[int] = mapped_column(sa.BigInteger)
    vwap: Mapped[float | None] = mapped_column(sa.Float)
    adjusted_at: Mapped[dt.datetime] = mapped_column(server_default=_NOW)
    provider: Mapped[str] = mapped_column(sa.Text)


class BarIntraday(Base):
    """Five-minute bar; 90-day retention (ADR-031)."""

    __tablename__ = "bars_intraday"
    __table_args__ = (Index("ix_bars_intraday_ts", "ts"),)

    symbol: Mapped[str] = mapped_column(sa.ForeignKey("tickers.symbol"), primary_key=True)
    ts: Mapped[dt.datetime] = mapped_column(primary_key=True)
    open: Mapped[float] = mapped_column(sa.Float)
    high: Mapped[float] = mapped_column(sa.Float)
    low: Mapped[float] = mapped_column(sa.Float)
    close: Mapped[float] = mapped_column(sa.Float)
    volume: Mapped[int] = mapped_column(sa.BigInteger)
    provider: Mapped[str] = mapped_column(sa.Text)


class CorporateAction(Base):
    """A split or dividend; a new split row triggers a full adjusted-history refetch."""

    __tablename__ = "corporate_actions"
    __table_args__ = (sa.CheckConstraint(_in("kind", ("split", "dividend")), name="kind"),)

    symbol: Mapped[str] = mapped_column(sa.ForeignKey("tickers.symbol"), primary_key=True)
    ex_date: Mapped[dt.date] = mapped_column(sa.Date, primary_key=True)
    kind: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    ratio: Mapped[float | None] = mapped_column(sa.Float)
    amount: Mapped[float | None] = mapped_column(sa.Float)
    first_seen_at: Mapped[dt.datetime] = mapped_column(server_default=_NOW)


class Fundamental(Base):
    """Point-in-time fundamentals keyed by `known_at`."""

    __tablename__ = "fundamentals"
    __table_args__ = (Index("ix_fundamentals_symbol_known_at", "symbol", "known_at"),)

    symbol: Mapped[str] = mapped_column(sa.ForeignKey("tickers.symbol"), primary_key=True)
    period_end: Mapped[dt.date] = mapped_column(sa.Date, primary_key=True)
    known_at: Mapped[dt.datetime] = mapped_column(primary_key=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)
    provider: Mapped[str] = mapped_column(sa.Text)


class EarningsCalendar(Base):
    """An earnings date for a symbol."""

    __tablename__ = "earnings_calendar"

    symbol: Mapped[str] = mapped_column(sa.ForeignKey("tickers.symbol"), primary_key=True)
    date: Mapped[dt.date] = mapped_column(sa.Date, primary_key=True)
    confirmed: Mapped[bool] = mapped_column(server_default=sa.false())
    known_at: Mapped[dt.datetime] = mapped_column(server_default=_NOW)


class ConfigVersion(Base):
    """A validated scoring config document, keyed by its hash. Append-only."""

    __tablename__ = "config_versions"
    __table_args__ = (sa.CheckConstraint(r"hash ~ '^sha256:[0-9a-f]{64}$'", name="hash_format"),)

    hash: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    version: Mapped[int] = mapped_column(sa.Integer)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    first_seen_at: Mapped[dt.datetime] = mapped_column(server_default=_NOW)


class Run(Base):
    """A daily run and its state (section 8)."""

    __tablename__ = "runs"
    __table_args__ = (
        sa.CheckConstraint(_ULID, name="id_ulid"),
        sa.CheckConstraint(_in("state", RUN_STATES), name="state"),
        sa.CheckConstraint(
            _in("trigger", ("schedule", "api", "mcp", "cli", "demo")), name="trigger"
        ),
        sa.CheckConstraint("(state = 'published') = (published_at IS NOT NULL)", name="published"),
        Index("ix_runs_trade_date_published_at", "trade_date", "published_at"),
        Index(
            "ux_runs_one_active",
            sa.text("(1)"),
            unique=True,
            postgresql_where=sa.text("state NOT IN ('published', 'failed')"),
        ),
        Index(
            "ux_runs_one_current_per_date",
            "trade_date",
            unique=True,
            postgresql_where=sa.text("published_at IS NOT NULL AND superseded_by IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    trade_date: Mapped[dt.date] = mapped_column(sa.Date)
    state: Mapped[str] = mapped_column(sa.Text, server_default="queued")
    trigger: Mapped[str] = mapped_column(sa.Text)
    config_hash: Mapped[str] = mapped_column(sa.ForeignKey("config_versions.hash"))
    code_version: Mapped[str] = mapped_column(sa.Text)
    market_regime: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=_NOW)
    started_at: Mapped[dt.datetime | None]
    finished_at: Mapped[dt.datetime | None]
    published_at: Mapped[dt.datetime | None]
    superseded_by: Mapped[str | None] = mapped_column(sa.ForeignKey("runs.id"))
    error_code: Mapped[str | None] = mapped_column(sa.Text)
    error_detail: Mapped[str | None] = mapped_column(sa.Text)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=_EMPTY_OBJECT)


class RunTransition(Base):
    """One state transition of a run. Append-only."""

    __tablename__ = "run_transitions"

    run_id: Mapped[str] = mapped_column(sa.ForeignKey("runs.id"), primary_key=True)
    seq: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    from_state: Mapped[str | None] = mapped_column(sa.Text)
    to_state: Mapped[str] = mapped_column(sa.Text)
    at: Mapped[dt.datetime] = mapped_column(server_default=_NOW)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=_EMPTY_OBJECT)


class IndicatorSnapshot(Base):
    """Indicator values at bar t for one symbol in one run. Append-only."""

    __tablename__ = "indicator_snapshots"

    run_id: Mapped[str] = mapped_column(sa.ForeignKey("runs.id"), primary_key=True)
    symbol: Mapped[str] = mapped_column(sa.ForeignKey("tickers.symbol"), primary_key=True)
    values: Mapped[dict[str, Any]] = mapped_column(JSONB)


class TickerScore(Base):
    """Per-ticker score, rank, and exclusion for a run. Append-only."""

    __tablename__ = "ticker_scores"
    __table_args__ = (
        sa.CheckConstraint(_in("status", ("scored", "excluded")), name="status"),
        sa.CheckConstraint("status = 'scored' OR exclusion_reason IS NOT NULL", name="exclusion"),
        Index("ix_ticker_scores_symbol_run", "symbol", "run_id"),
    )

    run_id: Mapped[str] = mapped_column(sa.ForeignKey("runs.id"), primary_key=True)
    symbol: Mapped[str] = mapped_column(sa.ForeignKey("tickers.symbol"), primary_key=True)
    status: Mapped[str] = mapped_column(sa.Text)
    exclusion_reason: Mapped[str | None] = mapped_column(sa.Text)
    data_quality: Mapped[str] = mapped_column(sa.Text)
    composite: Mapped[float | None] = mapped_column(sa.Float)
    display_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(4, 1))
    band: Mapped[str | None] = mapped_column(sa.Text)
    confidence: Mapped[float | None] = mapped_column(sa.Float)
    regime: Mapped[str | None] = mapped_column(sa.Text)
    st_dir_d: Mapped[int | None] = mapped_column(sa.SmallInteger)
    st_dir_w: Mapped[int | None] = mapped_column(sa.SmallInteger)
    bars_since_flip: Mapped[int | None] = mapped_column(sa.Integer)
    st_line: Mapped[float | None] = mapped_column(sa.Float)
    buy_threshold: Mapped[Decimal | None] = mapped_column(sa.Numeric(4, 1))
    sell_threshold: Mapped[Decimal | None] = mapped_column(sa.Numeric(4, 1))
    candidate: Mapped[str | None] = mapped_column(sa.Text)
    rank_overall: Mapped[int | None] = mapped_column(sa.Integer)
    weights: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    adjustments: Mapped[list[Any]] = mapped_column(JSONB, server_default=_EMPTY_ARRAY)
    flags: Mapped[list[Any]] = mapped_column(JSONB, server_default=_EMPTY_ARRAY)
    avg_dollar_volume_20d: Mapped[float | None] = mapped_column(sa.Float)
    rel_volume: Mapped[float | None] = mapped_column(sa.Float)


class FactorScore(Base):
    """One factor's score for one ticker in one run. Append-only."""

    __tablename__ = "factor_scores"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "symbol"], ["ticker_scores.run_id", "ticker_scores.symbol"]
        ),
        sa.CheckConstraint("score BETWEEN -100 AND 100", name="score_range"),
        Index("ix_factor_scores_symbol_run", "symbol", "run_id"),
    )

    run_id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    symbol: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    factor_id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    score: Mapped[float | None] = mapped_column(sa.Float)
    weight: Mapped[float] = mapped_column(sa.Float)
    contribution: Mapped[float] = mapped_column(sa.Float)
    quality: Mapped[str] = mapped_column(sa.Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Recommendation(Base):
    """A published pick. Append-only except `entry_price` and `entry_date` (set once)."""

    __tablename__ = "recommendations"
    __table_args__ = (
        sa.UniqueConstraint("run_id", "side", "rank", name="ix_recommendations_run_side_rank"),
        sa.UniqueConstraint("run_id", "symbol"),
        sa.CheckConstraint(_ULID, name="id_ulid"),
        sa.CheckConstraint(_in("side", ("buy", "sell")), name="side"),
        sa.CheckConstraint("rank >= 1", name="rank"),
        Index("ix_recommendations_symbol_trade_date", "symbol", "trade_date"),
    )

    id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(sa.ForeignKey("runs.id"))
    symbol: Mapped[str] = mapped_column(sa.ForeignKey("tickers.symbol"))
    trade_date: Mapped[dt.date] = mapped_column(sa.Date)
    side: Mapped[str] = mapped_column(sa.Text)
    rank: Mapped[int] = mapped_column(sa.SmallInteger)
    display_score: Mapped[Decimal] = mapped_column(sa.Numeric(4, 1))
    confidence: Mapped[float] = mapped_column(sa.Float)
    band: Mapped[str] = mapped_column(sa.Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)
    entry_price: Mapped[float | None] = mapped_column(sa.Float)
    entry_date: Mapped[dt.date | None] = mapped_column(sa.Date)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=_NOW)


class Narrative(Base):
    """Narrative text for a recommendation. Append-only."""

    __tablename__ = "narratives"
    __table_args__ = (
        sa.CheckConstraint(_in("source", ("llm", "template")), name="source"),
        sa.CheckConstraint("char_length(text) <= 1200", name="text_length"),
    )

    recommendation_id: Mapped[str] = mapped_column(
        sa.ForeignKey("recommendations.id"), primary_key=True
    )
    text: Mapped[str] = mapped_column(sa.Text)
    source: Mapped[str] = mapped_column(sa.Text)
    model: Mapped[str | None] = mapped_column(sa.Text)
    prompt_version: Mapped[str] = mapped_column(sa.Text)
    tokens_in: Mapped[int | None] = mapped_column(sa.Integer)
    tokens_out: Mapped[int | None] = mapped_column(sa.Integer)
    attempts: Mapped[int] = mapped_column(sa.SmallInteger, server_default="1")
    rejection_reasons: Mapped[list[Any]] = mapped_column(JSONB, server_default=_EMPTY_ARRAY)


class Outcome(Base):
    """Forward return of a recommendation at one horizon. Append-only."""

    __tablename__ = "outcomes"
    __table_args__ = (sa.CheckConstraint("horizon_days IN (1, 5, 10, 20)", name="horizon"),)

    recommendation_id: Mapped[str] = mapped_column(
        sa.ForeignKey("recommendations.id"), primary_key=True
    )
    horizon_days: Mapped[int] = mapped_column(sa.SmallInteger, primary_key=True)
    exit_date: Mapped[dt.date] = mapped_column(sa.Date)
    pick_return: Mapped[float] = mapped_column(sa.Float)
    benchmark_return: Mapped[float] = mapped_column(sa.Float)
    excess_return: Mapped[float] = mapped_column(sa.Float)
    adjustment_factor: Mapped[float] = mapped_column(sa.Float, server_default="1.0")
    computed_at: Mapped[dt.datetime] = mapped_column(server_default=_NOW)


class ProviderCall(Base):
    """One vendor HTTP call (never a URL with a key). 30-day retention."""

    __tablename__ = "provider_calls"
    __table_args__ = (
        Index("ix_provider_calls_ts", "ts"),
        Index("ix_provider_calls_provider_ts", "provider", "ts"),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(sa.ForeignKey("runs.id", ondelete="SET NULL"))
    provider: Mapped[str] = mapped_column(sa.Text)
    endpoint: Mapped[str] = mapped_column(sa.Text)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=_EMPTY_OBJECT)
    status: Mapped[str] = mapped_column(sa.Text)
    duration_ms: Mapped[int] = mapped_column(sa.Integer)
    cache_hit: Mapped[bool] = mapped_column(server_default=sa.false())
    ts: Mapped[dt.datetime] = mapped_column(server_default=_NOW)


class MetricCounter(Base):
    """A persisted monotonic counter (ADR-023)."""

    __tablename__ = "metric_counters"

    name: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    labels: Mapped[dict[str, Any]] = mapped_column(
        JSONB, primary_key=True, server_default=_EMPTY_OBJECT
    )
    value: Mapped[float] = mapped_column(sa.Float, server_default="0")
    updated_at: Mapped[dt.datetime] = mapped_column(server_default=_NOW)


class BacktestRun(Base):
    """A hypothetical backtest run (ADR-029). Deletable; never part of the published record."""

    __tablename__ = "backtest_runs"
    __table_args__ = (
        sa.CheckConstraint(_ULID, name="id_ulid"),
        sa.CheckConstraint(_in("state", ("running", "completed", "failed")), name="state"),
        {"schema": BACKTEST_SCHEMA},
    )

    id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    from_date: Mapped[dt.date] = mapped_column(sa.Date)
    to_date: Mapped[dt.date] = mapped_column(sa.Date)
    config_hash: Mapped[str] = mapped_column(sa.ForeignKey("config_versions.hash"))
    code_version: Mapped[str] = mapped_column(sa.Text)
    state: Mapped[str] = mapped_column(sa.Text)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=_NOW)
    finished_at: Mapped[dt.datetime | None]
    tickers: Mapped[int] = mapped_column(sa.Integer)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=_EMPTY_OBJECT)
    error_detail: Mapped[str | None] = mapped_column(sa.Text)


class BacktestPick(Base):
    """A hypothetical pick."""

    __tablename__ = "picks"
    __table_args__ = {"schema": BACKTEST_SCHEMA}  # noqa: RUF012

    backtest_id: Mapped[str] = mapped_column(
        sa.ForeignKey("backtests.backtest_runs.id", ondelete="CASCADE"), primary_key=True
    )
    trade_date: Mapped[dt.date] = mapped_column(sa.Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(sa.Text)
    side: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    rank: Mapped[int] = mapped_column(sa.SmallInteger, primary_key=True)
    display_score: Mapped[Decimal] = mapped_column(sa.Numeric(4, 1))
    confidence: Mapped[float] = mapped_column(sa.Float)
    band: Mapped[str] = mapped_column(sa.Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)
    entry_price: Mapped[float | None] = mapped_column(sa.Float)
    entry_date: Mapped[dt.date | None] = mapped_column(sa.Date)


class BacktestOutcome(Base):
    """A hypothetical pick's forward return at one horizon."""

    __tablename__ = "outcomes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["backtest_id", "trade_date", "side", "rank"],
            [
                "backtests.picks.backtest_id",
                "backtests.picks.trade_date",
                "backtests.picks.side",
                "backtests.picks.rank",
            ],
            ondelete="CASCADE",
        ),
        {"schema": BACKTEST_SCHEMA},
    )

    backtest_id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    trade_date: Mapped[dt.date] = mapped_column(sa.Date, primary_key=True)
    side: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    rank: Mapped[int] = mapped_column(sa.SmallInteger, primary_key=True)
    horizon_days: Mapped[int] = mapped_column(sa.SmallInteger, primary_key=True)
    pick_return: Mapped[float] = mapped_column(sa.Float)
    benchmark_return: Mapped[float] = mapped_column(sa.Float)
    excess_return: Mapped[float] = mapped_column(sa.Float)


class BacktestEquity(Base):
    """One point on a hypothetical equity curve."""

    __tablename__ = "equity_curve"
    __table_args__ = {"schema": BACKTEST_SCHEMA}  # noqa: RUF012

    backtest_id: Mapped[str] = mapped_column(
        sa.ForeignKey("backtests.backtest_runs.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[dt.date] = mapped_column(sa.Date, primary_key=True)
    strategy_equity: Mapped[float] = mapped_column(sa.Float)
    benchmark_equity: Mapped[float] = mapped_column(sa.Float)
