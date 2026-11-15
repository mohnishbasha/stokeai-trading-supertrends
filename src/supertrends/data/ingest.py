# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Ingestion service (PRD FR-101 to FR-118; ARCHITECTURE section 4, section 5).

`ingest(...)` is the one function used by `supertrends ingest` and by the daily run:

1. resolve the target session on the XNYS calendar (a holiday resolves to the prior session);
2. per ticker, in its own transaction so one failure never stops the others (FR-118):
   record corporate actions; on a newly seen split refetch and replace the ticker's full
   adjusted daily history (FR-105); otherwise fetch only bars after the last stored bar and
   upsert them (FR-104);
3. fetch regular-session 5-minute bars when the provider supports them (FR-103);
4. refresh point-in-time fundamentals and earnings dates when due (FR-115, FR-116);
5. run the data-quality pass (FR-107, FR-108) and return the result per ticker.

Upserts only touch rows whose values changed, so a second run changes nothing. Weekly bars are
not stored (ADR-033); see `supertrends.data.resample`.
"""

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Engine, Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from supertrends.data.calendar import last_completed_session
from supertrends.data.db import session_scope
from supertrends.data.ingest_plan import (
    BACKFILL_DAYS,
    bar_date,
    daily_window,
    fundamentals_due,
    intraday_window,
    new_splits,
    regular_session_only,
    resolve_as_of,
)
from supertrends.data.models import (
    BarDaily,
    BarIntraday,
    CorporateAction,
    EarningsCalendar,
    Fundamental,
    Ticker,
    WatchlistItem,
)
from supertrends.data.providers.base import (
    Bar,
    FundamentalsProvider,
    MarketDataProvider,
    validate_bar,
)
from supertrends.data.quality import Quality, classify_quality
from supertrends.errors import IngestError, ProviderDataError, ProviderError

log = logging.getLogger("supertrends.ingest")

BENCHMARKS = ("SPY", "QQQ")
FUNDAMENTALS_HISTORY_DAYS = 5 * 366
EARNINGS_LOOKBACK_DAYS = 120
EARNINGS_LOOKAHEAD_DAYS = 180
INSERT_CHUNK = 1000
_NOT_INGESTED = ("unresolved", "skipped")

_Row = dict[str, Any]


@dataclass
class TickerResult:
    """What ingestion did for one ticker."""

    symbol: str
    status: str = "ok"  # ok | partial | error | unresolved | skipped
    daily_rows: int = 0
    intraday_rows: int = 0
    actions_recorded: int = 0
    fundamentals_rows: int = 0
    earnings_rows: int = 0
    split_refetch: bool = False
    quality: Quality = "insufficient_history"
    errors: list[str] = field(default_factory=list)


@dataclass
class IngestSummary:
    """Result of one ingestion pass."""

    as_of: date
    provider: str
    results: list[TickerResult]

    @property
    def quality(self) -> dict[str, Quality]:
        """Data-quality status per ticker (the run stores it in `ticker_scores`)."""
        return {r.symbol: r.quality for r in self.results if r.status not in _NOT_INGESTED}

    @property
    def quality_counts(self) -> dict[str, int]:
        """Number of tickers per data-quality status."""
        counts: dict[str, int] = {}
        for status in self.quality.values():
            counts[status] = counts.get(status, 0) + 1
        return counts

    @property
    def rows_written(self) -> int:
        """Total bars, actions, fundamentals, and earnings rows inserted or changed."""
        return sum(
            r.daily_rows
            + r.intraday_rows
            + r.actions_recorded
            + r.fundamentals_rows
            + r.earnings_rows
            for r in self.results
        )


def default_symbols(session: Session) -> list[str]:
    """Symbols to ingest by default: resolved, non-crypto, non-index watchlist items plus
    the SPY and QQQ benchmarks.

    Differs from `watchlist.symbols_to_ingest` only in excluding index symbols such as VIX,
    following ARCHITECTURE section 6 "Exclusions"; PRD FR-009 allows ingesting VIX when the
    provider offers it. Unify once that conflict is decided (docs/GATE_DEBT.md GD-013).
    """
    rows = session.scalars(
        sa.select(WatchlistItem.symbol)
        .join(Ticker, Ticker.symbol == WatchlistItem.symbol)
        .where(Ticker.resolution == "resolved", Ticker.type.not_in(("crypto", "index")))
    )
    return sorted({*rows, *BENCHMARKS})


def _chunks(rows: Sequence[_Row]) -> Iterable[Sequence[_Row]]:
    for i in range(0, len(rows), INSERT_CHUNK):
        yield rows[i : i + INSERT_CHUNK]


def _upsert_changed(
    session: Session,
    table: Table,
    rows: Sequence[_Row],
    keys: Sequence[str],
    *,
    touch: dict[str, Any] | None = None,
) -> int:
    """INSERT ... ON CONFLICT (keys) DO UPDATE only where a value differs. Returns rows changed."""
    changed = 0
    for chunk in _chunks(rows):
        stmt = insert(table).values(list(chunk))
        value_cols = [c.name for c in table.columns if c.name in chunk[0] and c.name not in keys]
        stmt = stmt.on_conflict_do_update(
            index_elements=list(keys),
            set_={**{c: stmt.excluded[c] for c in value_cols}, **(touch or {})},
            where=sa.or_(*(table.c[c].is_distinct_from(stmt.excluded[c]) for c in value_cols)),
        )
        changed += len(session.execute(stmt.returning(sa.literal(1))).all())
    return changed


def _insert_ignore(session: Session, table: Table, rows: Sequence[_Row]) -> int:
    changed = 0
    for chunk in _chunks(rows):
        stmt = insert(table).values(list(chunk)).on_conflict_do_nothing()
        changed += len(session.execute(stmt.returning(sa.literal(1))).all())
    return changed


def _daily_rows(symbol: str, provider: str, bars: Iterable[Bar], as_of: date) -> list[_Row]:
    by_date: dict[date, _Row] = {}
    for raw in bars:
        bar = validate_bar(raw)
        day = bar_date(bar)
        if bar.symbol != symbol or day > as_of:
            continue
        by_date[day] = {
            "symbol": symbol,
            "date": day,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "vwap": bar.vwap,
            "provider": provider,
        }
    return [by_date[d] for d in sorted(by_date)]


def _ensure_ticker(session: Session, market: MarketDataProvider, symbol: str) -> str | None:
    """Make sure a `tickers` row exists. Returns None when ready, else the skip status."""
    ticker = session.get(Ticker, symbol)
    if ticker is None:
        info = market.resolve_symbol(symbol)
        if info is None:
            return "unresolved"
        if info.type in ("crypto", "index"):
            return "skipped"
        session.add(
            Ticker(
                symbol=symbol,
                name=info.name,
                type=info.type,
                active=info.active,
                is_benchmark=symbol in BENCHMARKS,
            )
        )
        session.flush()
        return None
    if ticker.resolution != "resolved":
        return "unresolved"
    if ticker.type in ("crypto", "index"):
        return "skipped"
    if symbol in BENCHMARKS and not ticker.is_benchmark:
        ticker.is_benchmark = True
    return None


def _ingest_daily(  # noqa: PLR0913
    session: Session,
    market: MarketDataProvider,
    symbol: str,
    as_of: date,
    *,
    full: bool,
    result: TickerResult,
) -> None:
    last_bar = session.scalar(
        sa.select(sa.func.max(BarDaily.date)).where(BarDaily.symbol == symbol)
    )
    known = {
        (ex, kind)
        for ex, kind in session.execute(
            sa.select(CorporateAction.ex_date, CorporateAction.kind).where(
                CorporateAction.symbol == symbol
            )
        )
    }
    actions = market.corporate_actions(symbol, as_of - timedelta(days=BACKFILL_DAYS), as_of)
    splits = new_splits(known, actions)
    refetch = full or (bool(splits) and last_bar is not None)
    if actions:
        action_rows = [
            {
                "symbol": symbol,
                "ex_date": a.ex_date,
                "kind": a.kind,
                "ratio": a.ratio,
                "amount": a.amount,
            }
            for a in actions
        ]
        result.actions_recorded = _insert_ignore(
            session,
            CorporateAction.__table__,  # type: ignore[arg-type]
            action_rows,
        )
    window = daily_window(last_bar, as_of, full=refetch)
    if window is None:
        return
    rows = _daily_rows(symbol, market.name, market.daily_bars(symbol, *window), as_of)
    if refetch:
        if not rows:
            msg = f"empty full-history refetch for {symbol}; keeping stored bars"
            raise ProviderDataError(msg)
        log.info("split_refetch symbol=%s new_splits=%d full=%s", symbol, len(splits), full)
        session.execute(sa.delete(BarDaily).where(BarDaily.symbol == symbol))
        result.split_refetch = True
    result.daily_rows = _upsert_changed(
        session,
        BarDaily.__table__,  # type: ignore[arg-type]
        rows,
        ("symbol", "date"),
        touch={"adjusted_at": sa.func.now()},
    )


def _ingest_intraday(
    session: Session, market: MarketDataProvider, symbol: str, as_of: date, result: TickerResult
) -> None:
    last_ts = session.scalar(
        sa.select(sa.func.max(BarIntraday.ts)).where(BarIntraday.symbol == symbol)
    )
    window = intraday_window(last_ts, as_of)
    if window is None:
        return
    rows: dict[datetime, _Row] = {}
    for bar in regular_session_only(market.intraday_bars(symbol, *window)):
        validate_bar(bar)
        ts = (bar.ts if bar.ts.tzinfo else bar.ts.replace(tzinfo=UTC)).astimezone(UTC)
        rows[ts] = {
            "symbol": symbol,
            "ts": ts,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "provider": market.name,
        }
    result.intraday_rows = _upsert_changed(
        session,
        BarIntraday.__table__,  # type: ignore[arg-type]
        [rows[t] for t in sorted(rows)],
        ("symbol", "ts"),
    )


def _ingest_fundamentals(  # noqa: PLR0913
    session: Session,
    fundamentals: FundamentalsProvider,
    symbol: str,
    as_of: date,
    *,
    full: bool,
    result: TickerResult,
) -> None:
    stored = session.scalar(
        sa.select(sa.func.count()).select_from(Fundamental).where(Fundamental.symbol == symbol)
    )
    known_earnings = set(
        session.scalars(sa.select(EarningsCalendar.date).where(EarningsCalendar.symbol == symbol))
    )
    if not fundamentals_due(
        has_rows=bool(stored), as_of=as_of, earnings_dates=known_earnings, full=full
    ):
        return
    since = as_of - timedelta(days=FUNDAMENTALS_HISTORY_DAYS)
    quarters = [
        {
            "symbol": symbol,
            "period_end": q.period_end,
            "known_at": q.known_at,
            "metrics": q.metrics,
            "provider": fundamentals.name,
        }
        for q in fundamentals.quarterly_financials(symbol, since)
        if q.symbol == symbol
    ]
    result.fundamentals_rows = _insert_ignore(
        session,
        Fundamental.__table__,  # type: ignore[arg-type]
        quarters,
    )
    dates = {
        e.date: {"symbol": symbol, "date": e.date, "confirmed": e.confirmed}
        for e in fundamentals.earnings_dates(
            symbol,
            as_of - timedelta(days=EARNINGS_LOOKBACK_DAYS),
            as_of + timedelta(days=EARNINGS_LOOKAHEAD_DAYS),
        )
        if e.symbol == symbol
    }
    result.earnings_rows = _upsert_changed(
        session,
        EarningsCalendar.__table__,  # type: ignore[arg-type]
        [dates[d] for d in sorted(dates)],
        ("symbol", "date"),
    )


def data_quality(session: Session, symbols: Sequence[str], as_of: date) -> dict[str, Quality]:
    """Data-quality status for each symbol from its stored daily bars (FR-107, FR-108)."""
    by_symbol: dict[str, list[date]] = {s: [] for s in symbols}
    for symbol, day in session.execute(
        sa.select(BarDaily.symbol, BarDaily.date)
        .where(BarDaily.symbol.in_(list(symbols)))
        .order_by(BarDaily.symbol, BarDaily.date)
    ):
        by_symbol[symbol].append(day)
    return {s: classify_quality(d, as_of) for s, d in by_symbol.items()}


def ingest(  # noqa: PLR0913 (explicit keyword arguments keep call sites readable)
    engine: Engine,
    market: MarketDataProvider,
    fundamentals: FundamentalsProvider | None,
    symbols: Iterable[str],
    *,
    as_of: date | None = None,
    full: bool = False,
    now: datetime | None = None,
) -> IngestSummary:
    """Ingest `symbols` up to the session `as_of` (default: the last completed session).

    Provider errors are isolated per ticker (FR-118): the ticker keeps its stored bars and is
    reported with an error; the rest continue. When every ticker fails because of the
    provider, `IngestError` (code `provider_unavailable`) is raised.
    """
    target = resolve_as_of(as_of, last_completed_session(now))
    wanted = sorted({s.strip().upper() for s in symbols if s.strip()})
    results = [TickerResult(symbol) for symbol in wanted]
    for result in results:
        _ingest_symbol(engine, market, fundamentals, result, target, full=full)
    ready = [r.symbol for r in results if r.status not in _NOT_INGESTED]
    if ready:
        with session_scope(engine) as session:
            statuses = data_quality(session, ready, target)
        for result in results:
            if result.symbol in statuses:
                result.quality = statuses[result.symbol]
        failed = [r for r in results if r.status == "error"]
        if len(failed) == len(ready):
            msg = f"provider unavailable for all {len(ready)} tickers: {failed[0].errors[0]}"
            raise IngestError(msg, code="provider_unavailable")
    return IngestSummary(as_of=target, provider=market.name, results=results)


def _ingest_symbol(  # noqa: PLR0913
    engine: Engine,
    market: MarketDataProvider,
    fundamentals: FundamentalsProvider | None,
    result: TickerResult,
    as_of: date,
    *,
    full: bool,
) -> None:
    symbol = result.symbol
    try:
        with session_scope(engine) as session:
            skip = _ensure_ticker(session, market, symbol)
            if skip is not None:
                result.status = skip
                return
            _ingest_daily(session, market, symbol, as_of, full=full, result=result)
    except ProviderError as exc:
        result.status = "error"
        result.errors.append(f"daily: {type(exc).__name__}: {exc}")
        return
    steps: list[tuple[str, Callable[[Session], None]]] = []
    if market.capabilities.intraday:
        steps.append(("intraday", lambda s: _ingest_intraday(s, market, symbol, as_of, result)))
    if fundamentals is not None:
        steps.append(
            (
                "fundamentals",
                lambda s: _ingest_fundamentals(
                    s, fundamentals, symbol, as_of, full=full, result=result
                ),
            )
        )
    for name, step in steps:
        try:
            with session_scope(engine) as session:
                step(session)
        except ProviderError as exc:
            result.status = "partial"
            result.errors.append(f"{name}: {type(exc).__name__}: {exc}")
