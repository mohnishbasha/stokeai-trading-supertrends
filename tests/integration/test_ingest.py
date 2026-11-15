# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Ingestion against real Postgres with the fixture provider (PRD FR-101 to FR-118).

Runs only when SUPERTRENDS_IT_DATABASE_URL is set. Every test starts from an empty database.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest
from alembic import command
from sqlalchemy import Engine, text
from typer.testing import CliRunner

from supertrends.cli.main import app
from supertrends.data import db
from supertrends.data.call_recorder import CallRecord, DbCallRecorder
from supertrends.data.ingest import default_symbols, ingest
from supertrends.data.providers.base import (
    Bar,
    CorporateAction,
    ProviderCapabilities,
    ProviderStatus,
    SymbolInfo,
)
from supertrends.data.providers.fixture import (
    DAILY_SESSIONS,
    FixtureFundamentals,
    FixtureProvider,
    FixtureUniverse,
)
from supertrends.errors import IngestError, ProviderUnavailable

URL = os.environ.get("SUPERTRENDS_IT_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="set SUPERTRENDS_IT_DATABASE_URL to run")

SEED = 20261114
END = date(2026, 11, 13)
SYMBOLS = ["FXA", "FXE", "FXK", "SPY"]
TABLES = ("tickers", "bars_daily", "bars_intraday", "corporate_actions", "fundamentals")


def _downgrade_base(engine: Engine) -> None:
    config = db.alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = db.create_db_engine(url=URL)
    _downgrade_base(eng)
    db.migrate(eng)
    yield eng
    _downgrade_base(eng)
    eng.dispose()


def _universe(end: date = END) -> FixtureUniverse:
    return FixtureUniverse(seed=SEED, end_date=end)


class Spy:
    """Delegating market provider that records calls and can inject faults."""

    def __init__(self, inner: FixtureProvider) -> None:
        self.inner = inner
        self.name = inner.name
        self.capabilities: ProviderCapabilities = inner.capabilities
        self.calls: list[tuple[str, str, date | None, date | None]] = []
        self.fail_daily: set[str] = set()
        self.extra_splits: dict[str, CorporateAction] = {}
        self.price_scale: dict[str, float] = {}

    def daily_bars(self, symbol: str, start: date, end: date) -> Sequence[Bar]:
        self.calls.append(("daily_bars", symbol, start, end))
        if symbol in self.fail_daily:
            msg = "simulated outage"
            raise ProviderUnavailable(msg)
        scale = self.price_scale.get(symbol, 1.0)
        return [
            replace(
                b,
                open=b.open * scale,
                high=b.high * scale,
                low=b.low * scale,
                close=b.close * scale,
            )
            for b in self.inner.daily_bars(symbol, start, end)
        ]

    def grouped_daily(self, session: date) -> Sequence[Bar]:
        return self.inner.grouped_daily(session)

    def intraday_bars(self, symbol: str, start: date, end: date, minutes: Any = 5) -> Sequence[Bar]:
        self.calls.append(("intraday_bars", symbol, start, end))
        return self.inner.intraday_bars(symbol, start, end)

    def corporate_actions(self, symbol: str, start: date, end: date) -> Sequence[CorporateAction]:
        actions = list(self.inner.corporate_actions(symbol, start, end))
        if symbol in self.extra_splits:
            actions.append(self.extra_splits[symbol])
        return actions

    def resolve_symbol(self, symbol: str) -> SymbolInfo | None:
        return self.inner.resolve_symbol(symbol)

    def trades(self, symbol: str, session: date) -> Sequence[object]:
        return self.inner.trades(symbol, session)

    def status(self) -> ProviderStatus:
        return self.inner.status()

    def fetches(self) -> list[tuple[str, str, date | None, date | None]]:
        return [c for c in self.calls if c[0] in ("daily_bars", "intraday_bars")]


def _spy(end: date = END) -> Spy:
    return Spy(FixtureProvider(_universe(end)))


def _fund(end: date = END) -> FixtureFundamentals:
    return FixtureFundamentals(_universe(end))


def _snapshot(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    snap: dict[str, list[tuple[Any, ...]]] = {}
    with engine.connect() as conn:
        for table in (*TABLES, "earnings_calendar"):
            rows = conn.execute(text(f"SELECT * FROM {table} ORDER BY 1, 2")).all()
            snap[table] = [tuple(r) for r in rows]
    return snap


def _count(engine: Engine, sql: str, **params: object) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(sql), params).scalar_one())


def test_it_ingest_second_run_is_idempotent_no_row_changes(engine: Engine) -> None:
    spy = _spy()
    first = ingest(engine, spy, _fund(), SYMBOLS, as_of=END)
    assert first.rows_written > 0
    assert first.quality == dict.fromkeys(SYMBOLS, "ok")
    assert _count(engine, "SELECT count(*) FROM bars_daily WHERE symbol='FXA'") == DAILY_SESSIONS
    assert _count(engine, "SELECT count(*) FROM bars_intraday WHERE symbol='FXA'") > 0
    assert _count(engine, "SELECT count(*) FROM corporate_actions WHERE symbol='FXE'") == 1
    assert _count(engine, "SELECT count(*) FROM fundamentals WHERE symbol='FXA'") > 0
    assert _count(engine, "SELECT count(*) FROM fundamentals WHERE symbol='FXK'") == 0  # ETF
    assert _count(engine, "SELECT count(*) FROM tickers WHERE is_benchmark") == 1  # SPY

    before = _snapshot(engine)
    spy.calls.clear()
    second = ingest(engine, spy, _fund(), SYMBOLS, as_of=END)
    assert second.rows_written == 0
    assert spy.fetches() == []  # nothing new is requested
    assert _snapshot(engine) == before  # including adjusted_at and first_seen_at
    assert second.quality == first.quality


def test_it_ingest_intraday_keeps_regular_session_bars_only(engine: Engine) -> None:
    ingest(engine, _spy(), _fund(), ["FXA"], as_of=END)
    assert (
        _count(
            engine,
            "SELECT count(*) FROM bars_intraday WHERE "
            "(ts AT TIME ZONE 'America/New_York')::time < '09:30' OR "
            "(ts AT TIME ZONE 'America/New_York')::time >= '16:00'",
        )
        == 0
    )


def test_it_ingest_incremental_fetch_starts_from_last_stored_bar(engine: Engine) -> None:
    spy = _spy()
    ingest(engine, spy, _fund(), ["FXA"], as_of=date(2026, 11, 6))
    spy.calls.clear()
    summary = ingest(engine, spy, _fund(), ["FXA"], as_of=END)
    daily = [c for c in spy.calls if c[0] == "daily_bars"]
    assert daily == [("daily_bars", "FXA", date(2026, 11, 7), END)]
    assert summary.results[0].daily_rows == 5  # Nov 9 to 13
    assert _count(engine, "SELECT max(date) - min(date) FROM bars_daily") > 1000
    assert _count(engine, "SELECT count(*) FROM bars_daily") == DAILY_SESSIONS


def test_it_ingest_split_detected_triggers_full_adjusted_history_refetch(engine: Engine) -> None:
    spy = _spy()
    ingest(engine, spy, _fund(), ["FXE", "FXK"], as_of=END)
    before = _snapshot(engine)
    old_close = _count(
        engine, "SELECT close::int FROM bars_daily WHERE symbol='FXE' AND date=:d", d=END
    )

    spy.calls.clear()
    spy.extra_splits["FXE"] = CorporateAction("FXE", date(2026, 11, 12), "split", 2.0, None)
    spy.price_scale["FXE"] = 0.5  # the vendor now reports a re-adjusted series
    summary = ingest(engine, spy, _fund(), ["FXE", "FXK"], as_of=END)

    by_symbol = {r.symbol: r for r in summary.results}
    assert by_symbol["FXE"].split_refetch
    assert not by_symbol["FXK"].split_refetch
    daily = [c for c in spy.calls if c[0] == "daily_bars"]
    assert [c[1] for c in daily] == ["FXE"]  # only the split ticker is refetched
    start = daily[0][2]
    assert start is not None
    assert (END - start).days > 1000  # full history, not an increment
    after = _snapshot(engine)
    assert len(after["bars_daily"]) == len(before["bars_daily"])  # replaced, not duplicated
    new_close = _count(
        engine, "SELECT close::int FROM bars_daily WHERE symbol='FXE' AND date=:d", d=END
    )
    assert abs(new_close - old_close / 2) <= 1
    fxk_before = [r for r in before["bars_daily"] if r[0] == "FXK"]
    assert [r for r in after["bars_daily"] if r[0] == "FXK"] == fxk_before
    assert _count(engine, "SELECT count(*) FROM corporate_actions WHERE symbol='FXE'") == 2

    # The split is now known: a further run does not refetch again.
    spy.calls.clear()
    again = ingest(engine, spy, _fund(), ["FXE", "FXK"], as_of=END)
    assert not any(r.split_refetch for r in again.results)
    assert spy.fetches() == []


def test_it_ingest_provider_error_isolated_per_ticker_and_marks_stale(engine: Engine) -> None:
    spy = _spy()
    ingest(engine, spy, _fund(), ["FXA", "FXB"], as_of=date(2026, 11, 10))
    spy.fail_daily.add("FXA")
    summary = ingest(engine, spy, _fund(), ["FXA", "FXB"], as_of=END)
    by_symbol = {r.symbol: r for r in summary.results}
    assert by_symbol["FXA"].status == "error"
    assert by_symbol["FXA"].quality == "stale"  # keeps its stored bars, latest is older
    assert by_symbol["FXB"].status == "ok"
    assert by_symbol["FXB"].quality == "ok"


def test_it_ingest_all_tickers_failing_raises_provider_unavailable(engine: Engine) -> None:
    spy = _spy()
    spy.fail_daily.update(SYMBOLS)
    with pytest.raises(IngestError) as info:
        ingest(engine, spy, _fund(), SYMBOLS, as_of=END)
    assert info.value.code == "provider_unavailable"


def test_it_ingest_unresolved_symbol_is_reported_not_stored(engine: Engine) -> None:
    summary = ingest(engine, _spy(), _fund(), ["FXA", "ZZZZ9"], as_of=END)
    by_symbol = {r.symbol: r for r in summary.results}
    assert by_symbol["ZZZZ9"].status == "unresolved"
    assert "ZZZZ9" not in summary.quality
    assert _count(engine, "SELECT count(*) FROM tickers WHERE symbol='ZZZZ9'") == 0


def test_it_quality_gap_of_four_sessions_flags_degraded(engine: Engine) -> None:
    spy = _spy()
    ingest(engine, spy, _fund(), ["FXA"], as_of=END)
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM bars_daily WHERE symbol='FXA' AND date IN "
                "(SELECT date FROM bars_daily WHERE symbol='FXA' ORDER BY date DESC "
                "OFFSET 40 LIMIT 4)"
            )
        )
    summary = ingest(engine, FixtureOnlyNoFetch(spy), _fund(), ["FXA"], as_of=END)
    assert summary.quality["FXA"] == "degraded"


class FixtureOnlyNoFetch(Spy):
    """Provider whose daily_bars returns nothing, so the stored gap stays in place."""

    def __init__(self, inner: Spy) -> None:
        super().__init__(inner.inner)

    def daily_bars(self, symbol: str, start: date, end: date) -> Sequence[Bar]:
        return []


def test_it_quality_short_history_is_insufficient(engine: Engine) -> None:
    ingest(engine, _spy(), _fund(), ["FXA"], as_of=END)
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM bars_daily WHERE symbol='FXA' AND date <= "
                "(SELECT date FROM bars_daily WHERE symbol='FXA' ORDER BY date DESC "
                "OFFSET 248 LIMIT 1)"
            )
        )
    summary = ingest(engine, _spy(), _fund(), ["FXA"], as_of=END)
    assert summary.quality["FXA"] == "insufficient_history"  # 249 bars remain


def test_it_ingest_holiday_does_not_mark_tickers_stale(engine: Engine) -> None:
    thanksgiving = datetime(2026, 11, 26, 15, tzinfo=UTC)
    market = _spy(date(2026, 11, 25))
    summary = ingest(engine, market, _fund(date(2026, 11, 25)), SYMBOLS, now=thanksgiving)
    assert summary.as_of == date(2026, 11, 25)
    assert summary.quality == dict.fromkeys(SYMBOLS, "ok")
    market.calls.clear()
    again = ingest(engine, market, _fund(date(2026, 11, 25)), SYMBOLS, now=thanksgiving)
    assert again.rows_written == 0
    assert market.fetches() == []
    assert set(again.quality.values()) == {"ok"}


def test_it_ingest_half_day_after_thanksgiving_is_a_session(engine: Engine) -> None:
    friday_close = datetime(2026, 11, 27, 19, tzinfo=UTC)  # 14:00 ET, after the 13:00 close
    market = _spy(date(2026, 11, 27))
    summary = ingest(engine, market, _fund(date(2026, 11, 27)), ["FXA"], now=friday_close)
    assert summary.as_of == date(2026, 11, 27)
    assert summary.quality["FXA"] == "ok"
    assert _count(engine, "SELECT count(*) FROM bars_daily WHERE date='2026-11-27'") == 1
    # No 5-minute bar starts at or after the 13:00 ET early close (18:00 UTC).
    assert (
        _count(
            engine,
            "SELECT count(*) FROM bars_intraday WHERE ts >= '2026-11-27 18:00+00' "
            "AND ts < '2026-11-28'",
        )
        == 0
    )
    assert (
        _count(
            engine,
            "SELECT count(*) FROM bars_intraday "
            "WHERE ts >= '2026-11-27 17:55+00' AND ts < '2026-11-28'",
        )
        == 1
    )


def test_it_provider_calls_recorded_without_api_key_in_path_or_params(engine: Engine) -> None:
    secret = "FAKE-VALUE-12345"  # noqa: S105 (a fake marker, not a credential)
    recorder = DbCallRecorder(engine)
    recorder.record(
        CallRecord(
            provider="massive",
            endpoint=f"/v2/aggs/ticker/FXA/range/1/day/2026-01-01/2026-02-01?apiKey={secret}",
            params={"adjusted": "true", "apiKey": secret, "symbol": "FXA"},
            status=200,
            duration_ms=12.6,
            cache_hit=False,
        )
    )
    recorder.record(
        CallRecord("massive", "/v3/reference/splits", {}, None, 3.0, True),
    )
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT provider, endpoint, params, status, duration_ms, cache_hit "
                "FROM provider_calls ORDER BY id"
            )
        ).all()
        dump = (
            conn.execute(text("SELECT row_to_json(p)::text FROM provider_calls p")).scalars().all()
        )
    assert rows[0].status == "200"
    assert rows[0].duration_ms == 13
    assert rows[0].params == {"adjusted": "true", "symbol": "FXA"}
    assert "?" not in rows[0].endpoint
    assert (rows[1].status, rows[1].cache_hit) == ("error", True)
    assert secret not in "".join(dump)


def test_it_ingest_default_symbols_exclude_unresolved_and_crypto_and_add_benchmarks(
    engine: Engine,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO tickers (symbol, type, resolution) VALUES "
                "('AAA','stock','resolved'),('BBB','stock','unresolved'),"
                "('BTC','crypto','resolved'),('IDX','index','resolved')"
            )
        )
        conn.execute(text("INSERT INTO watchlists (name, is_default) VALUES ('default', true)"))
        conn.execute(
            text(
                "INSERT INTO watchlist_items (watchlist_id, symbol) "
                "SELECT id, s FROM watchlists, unnest(ARRAY['AAA','BBB','BTC','IDX']) s"
            )
        )
    with db.session_scope(engine) as session:
        assert default_symbols(session) == ["AAA", "QQQ", "SPY"]


def test_it_cli_ingest_fills_database_and_second_run_changes_nothing(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERTRENDS_DATABASE_URL", URL)
    monkeypatch.setenv("SUPERTRENDS_MARKET_PROVIDER", "fixture")
    monkeypatch.setenv("SUPERTRENDS_FUNDAMENTALS_PROVIDER", "fixture")
    monkeypatch.setenv("SUPERTRENDS_FIXTURE_SEED", str(SEED))
    monkeypatch.setenv("SUPERTRENDS_FIXTURE_END_DATE", END.isoformat())
    args = ["ingest", "--symbols", "FXA,FXE,fxk,SPY", "--date", END.isoformat()]
    runner = CliRunner()

    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    assert "quality: ok=4" in first.output
    assert "FXA" in first.output
    assert _count(engine, "SELECT count(*) FROM tickers") == 4
    assert _count(engine, "SELECT count(*) FROM bars_daily") == 4 * DAILY_SESSIONS
    before = _snapshot(engine)

    second = runner.invoke(app, args)
    assert second.exit_code == 0, second.output
    assert "daily=0 intraday=0 actions=0 fundamentals=0 earnings=0" in second.output
    assert _snapshot(engine) == before

    full = runner.invoke(app, [*args, "--full"])
    assert full.exit_code == 0, full.output
    assert "split-refetch" in full.output
    assert _count(engine, "SELECT count(*) FROM bars_daily") == 4 * DAILY_SESSIONS
