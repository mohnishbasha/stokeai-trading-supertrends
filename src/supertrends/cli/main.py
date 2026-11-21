# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""`supertrends` entry point (ARCHITECTURE section 6, CLI).

Sprint 0 commands: --version, serve, healthcheck, config show | validate | export-schema.
Sprint 1 adds db migrate, ingest, and watchlist. Sprint 3 adds run daily (ADR-066).
"""

import json
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import httpx
import typer
import yaml
from sqlalchemy.orm import Session

from supertrends.errors import ConfigError
from supertrends.scoring.config import config_hash, json_schema, load_scoring_config
from supertrends.settings import load_settings
from supertrends.version import LICENSE_NOTICE, get_commit, get_version, source_url

if TYPE_CHECKING:
    from datetime import date

    from supertrends.runs.orchestrator import RunOutcome

DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS = 3.0
CONFIG_INVALID_EXIT = 2
SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

app = typer.Typer(name="supertrends", no_args_is_help=True, add_completion=False)
config_app = typer.Typer(help="Show, validate, and export the scoring config.")
app.add_typer(config_app, name="config")
db_app = typer.Typer(help="Database operations (local mode only).")
app.add_typer(db_app, name="db")
watchlist_app = typer.Typer(help="Watchlist operations (local mode only).")
app.add_typer(watchlist_app, name="watchlist")
run_app = typer.Typer(help="Daily runs (local mode executes inline).")
app.add_typer(run_app, name="run")


class HealthExit(IntEnum):
    """Exit codes of `supertrends healthcheck`."""

    READY = 0
    UNREACHABLE = 1
    NOT_READY = 3


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"supertrends {get_version()} ({get_commit()})")
        typer.echo(f"{LICENSE_NOTICE} {source_url()}")
        raise typer.Exit


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Print version, commit, and the license notice.",
        ),
    ] = False,
) -> None:
    """Super Trends Market Agent. General market analysis, not investment advice."""


@app.command()
def serve(
    bind: Annotated[
        str | None, typer.Option(help="HOST:PORT to listen on (env SUPERTRENDS_BIND).")
    ] = None,
) -> None:
    """Run the HTTP API and serve the UI."""
    import uvicorn  # noqa: PLC0415 (keeps CLI start-up fast for other commands)

    settings = load_settings()
    _seed_on_first_start()
    host, _, port = (bind or settings.bind).rpartition(":")
    uvicorn.run(
        "supertrends.api.app:create_app",
        factory=True,
        host=host,
        port=int(port),
        log_level=settings.effective_log_level,
        proxy_headers=False,
    )


def _seed_on_first_start() -> None:
    """Seed the default watchlist when it does not exist; never blocks the server start."""
    from sqlalchemy.exc import SQLAlchemyError  # noqa: PLC0415 (keeps CLI start-up fast)

    from supertrends.data import watchlist as wl  # noqa: PLC0415

    try:
        result = wl.seed_if_empty(wl.PermissiveResolver())
    except (SQLAlchemyError, ConfigError) as exc:
        typer.echo(f"watchlist seed skipped: {type(exc).__name__}", err=True)
        return
    if result is not None:
        typer.echo(f"seeded watchlist: {result.groups} groups, {result.symbols} symbols", err=True)


@app.command()
def healthcheck(
    url: Annotated[str, typer.Option(help="Base URL of the API.")] = "http://127.0.0.1:8080",
    timeout: Annotated[float, typer.Option(help="Seconds.")] = DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS,
) -> None:
    """GET {url}/readyz. Exit 0 ready, 3 not ready, 1 unreachable."""
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{url.rstrip('/')}/readyz")
    except httpx.HTTPError as exc:
        typer.echo(f"unreachable: {type(exc).__name__}", err=True)
        raise typer.Exit(HealthExit.UNREACHABLE) from exc
    if response.status_code != httpx.codes.OK:
        typer.echo(f"not ready: HTTP {response.status_code}", err=True)
        raise typer.Exit(HealthExit.NOT_READY)
    typer.echo("ok")


def _config_path(path: Path | None) -> Path:
    return path if path is not None else Path(load_settings().scoring_config)


@config_app.command("validate")
def config_validate(
    path: Annotated[Path | None, typer.Argument(help="Config file (default: active).")] = None,
) -> None:
    """Print `valid sha256:<hash>`, or the errors and exit 2."""
    try:
        cfg = load_scoring_config(_config_path(path))
    except ConfigError as exc:
        for line in str(exc).split("; "):
            typer.echo(line)
        raise typer.Exit(CONFIG_INVALID_EXIT) from exc
    typer.echo(f"valid {config_hash(cfg)}")


@config_app.command("show")
def config_show(
    path: Annotated[Path | None, typer.Option(help="Config file (default: active).")] = None,
) -> None:
    """Print the validated config with its hash."""
    try:
        cfg = load_scoring_config(_config_path(path))
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(CONFIG_INVALID_EXIT) from exc
    typer.echo(f"# config_hash: {config_hash(cfg)}")
    typer.echo(yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False), nl=False)


@config_app.command("export-schema")
def config_export_schema(
    output: Annotated[
        Path | None, typer.Option(help="Write to this file instead of stdout.")
    ] = None,
) -> None:
    """Export the scoring config JSON schema."""
    text = json.dumps(json_schema(), indent=2, sort_keys=True) + "\n"
    if output is None:
        typer.echo(text, nl=False)
    else:
        output.write_text(text, encoding="utf-8")


@config_app.command("export-openapi")
def config_export_openapi(
    output: Annotated[
        Path | None, typer.Option(help="Write to this file instead of stdout.")
    ] = None,
) -> None:
    """Export the API's OpenAPI document (what `make openapi` commits to docs/openapi.json)."""
    from supertrends.api.openapi import render_openapi  # noqa: PLC0415 (keeps CLI start-up fast)

    text = render_openapi()
    if output is None:
        typer.echo(text, nl=False)
    else:
        output.write_text(text, encoding="utf-8")


@db_app.command("migrate")
def db_migrate(
    revision: Annotated[str, typer.Option(help="Target Alembic revision.")] = "head",
) -> None:
    """Apply migrations under an advisory lock and print the revision. Exit 3 if unreachable."""
    from sqlalchemy.exc import SQLAlchemyError  # noqa: PLC0415 (keeps CLI start-up fast)

    from supertrends.data import db  # noqa: PLC0415

    engine = db.create_db_engine()
    try:
        applied = db.migrate(engine, revision)
    except SQLAlchemyError as exc:
        typer.echo(f"database error: {type(exc).__name__}", err=True)
        raise typer.Exit(HealthExit.NOT_READY) from exc
    finally:
        engine.dispose()
    typer.echo(f"revision {applied}")


@contextmanager
def _watchlist_session() -> Iterator[Session]:
    from sqlalchemy.exc import SQLAlchemyError  # noqa: PLC0415 (keeps CLI start-up fast)

    from supertrends.data import db  # noqa: PLC0415

    engine = db.create_db_engine()
    try:
        with db.session_scope(engine) as session:
            yield session
    except SQLAlchemyError as exc:
        typer.echo(f"database error: {type(exc).__name__}", err=True)
        raise typer.Exit(HealthExit.NOT_READY) from exc
    finally:
        engine.dispose()


def _watchlist_call[T](action: Callable[[Session], T]) -> T:
    from supertrends.data.watchlist import WatchlistError  # noqa: PLC0415

    try:
        with _watchlist_session() as session:
            return action(session)
    except WatchlistError as exc:
        typer.echo(exc.detail, err=True)
        raise typer.Exit(CONFIG_INVALID_EXIT) from exc


@watchlist_app.command("seed")
def watchlist_seed() -> None:
    """Load config/watchlist.seed.yaml if the default watchlist does not exist yet."""
    from supertrends.data import watchlist as wl  # noqa: PLC0415

    result = _watchlist_call(lambda s: wl.seed_default_watchlist(s, wl.PermissiveResolver()))
    if result is None:
        typer.echo("watchlist already exists; not reseeded")
        return
    typer.echo(
        f"seeded {result.groups} groups and {result.symbols} symbols "
        f"({len(result.unresolved)} unresolved, {len(result.needs_review)} needs review, "
        f"{len(result.rejected)} not storable)"
    )


@watchlist_app.command("list")
def watchlist_list(
    as_json: Annotated[bool, typer.Option("--json", help="Print one JSON document.")] = False,
) -> None:
    """List groups and items."""
    from supertrends.api.schemas.watchlist import WatchlistResponse  # noqa: PLC0415
    from supertrends.data import watchlist as wl  # noqa: PLC0415

    view = _watchlist_call(wl.read_watchlist)
    if as_json:
        typer.echo(WatchlistResponse.model_validate(view, from_attributes=True).model_dump_json())
        return
    typer.echo(f"watchlist {view.name}: {view.count} of {view.max} tickers")
    for group in view.groups:
        typer.echo(f"{group.slug} ({group.name}): {' '.join(group.symbols)}")
    for item in view.items:
        if item.resolution != "resolved":
            typer.echo(f"{item.symbol}: {item.resolution} - {item.resolution_reason}")


@watchlist_app.command("add")
def watchlist_add(
    symbol: Annotated[str, typer.Argument(help="Ticker symbol.")],
    group: Annotated[list[str] | None, typer.Option(help="Group slug (repeatable).")] = None,
) -> None:
    """Add a symbol to the watchlist."""
    from supertrends.data import watchlist as wl  # noqa: PLC0415

    item = _watchlist_call(
        lambda s: wl.add_item(s, symbol, group or [], wl.PermissiveResolver(), source="cli")
    )
    typer.echo(f"added {item.symbol}")


@watchlist_app.command("remove")
def watchlist_remove(symbol: Annotated[str, typer.Argument(help="Ticker symbol.")]) -> None:
    """Remove a symbol from the watchlist."""
    from supertrends.data import watchlist as wl  # noqa: PLC0415

    _watchlist_call(lambda s: wl.remove_item(s, symbol))
    typer.echo(f"removed {symbol.upper()}")


@app.command()
def ingest(
    date_: Annotated[
        str | None,
        typer.Option("--date", help="Target session YYYY-MM-DD (default: last completed)."),
    ] = None,
    symbols: Annotated[
        str | None,
        typer.Option(help="Comma separated symbols (default: watchlist plus SPY and QQQ)."),
    ] = None,
    full: Annotated[
        bool, typer.Option("--full", help="Refetch the full adjusted history.")
    ] = False,
) -> None:
    """Ingest bars, corporate actions, fundamentals, and earnings; print quality counts.

    Local mode only. Idempotent: a second run for the same date changes nothing. Exit 2 on an
    invalid date or symbol, 3 when the database is unreachable, 1 on a provider outage.
    """
    from datetime import date  # noqa: PLC0415 (keeps CLI start-up fast)

    from sqlalchemy.exc import SQLAlchemyError  # noqa: PLC0415

    from supertrends.data import db  # noqa: PLC0415
    from supertrends.data.ingest import default_symbols  # noqa: PLC0415
    from supertrends.data.ingest import ingest as run_ingest  # noqa: PLC0415
    from supertrends.data.providers.registry import (  # noqa: PLC0415
        fundamentals_provider,
        market_provider,
    )
    from supertrends.errors import IngestError  # noqa: PLC0415

    try:
        target = date.fromisoformat(date_) if date_ else None
    except ValueError as exc:
        typer.echo(f"invalid --date: {date_}", err=True)
        raise typer.Exit(CONFIG_INVALID_EXIT) from exc
    wanted = [s.strip().upper() for s in symbols.split(",") if s.strip()] if symbols else None
    bad = [s for s in wanted or [] if not SYMBOL_RE.fullmatch(s)]
    if bad:
        typer.echo(f"invalid symbol: {', '.join(bad)}", err=True)
        raise typer.Exit(CONFIG_INVALID_EXIT)
    settings = load_settings()
    engine = db.create_db_engine(settings)
    try:
        if wanted is None:
            with db.session_scope(engine) as session:
                wanted = default_symbols(session)
        summary = run_ingest(
            engine,
            market_provider(settings),
            fundamentals_provider(settings),
            wanted,
            as_of=target,
            full=full,
        )
    except IngestError as exc:
        typer.echo(f"ingest failed ({exc.code}): {exc}", err=True)
        raise typer.Exit(1) from exc
    except SQLAlchemyError as exc:
        typer.echo(f"database error: {type(exc).__name__}", err=True)
        raise typer.Exit(HealthExit.NOT_READY) from exc
    finally:
        engine.dispose()
    typer.echo(f"ingest {summary.as_of} provider={summary.provider}")
    for r in summary.results:
        flags = " split-refetch" if r.split_refetch else ""
        detail = f" ({'; '.join(r.errors)})" if r.errors else ""
        typer.echo(
            f"{r.symbol:<6} {r.status:<10} quality={r.quality:<20} daily={r.daily_rows} "
            f"intraday={r.intraday_rows} actions={r.actions_recorded} "
            f"fundamentals={r.fundamentals_rows} earnings={r.earnings_rows}{flags}{detail}"
        )
    counts = " ".join(f"{k}={v}" for k, v in sorted(summary.quality_counts.items()))
    typer.echo(f"quality: {counts or 'none'}")


class RunExit(IntEnum):
    """Exit codes of `supertrends run daily` (ARCHITECTURE section 6, ADR-021, ADR-022)."""

    OK = 0
    FAILED = 1
    USAGE = 2
    NOT_NOW = 3


def _run_payload(outcome: "RunOutcome", picks: list[dict[str, object]]) -> dict[str, object]:
    active = outcome.active_trade_date
    return {
        "status": outcome.status,
        "trade_date": outcome.trade_date.isoformat(),
        "run_id": outcome.run_id,
        "summary": dict(outcome.summary),
        "error_code": outcome.error_code,
        "error_detail": outcome.error_detail,
        "active_run_id": outcome.active_run_id,
        "active_trade_date": None if active is None else active.isoformat(),
        "picks": picks,
    }


def _report_run(
    outcome: "RunOutcome", picks: list[dict[str, object]], trade_date: "date", *, as_json: bool
) -> None:
    """Print the outcome of `run daily` and exit with its code."""
    from supertrends.runs.narrator import DISCLAIMER  # noqa: PLC0415

    if as_json:
        typer.echo(json.dumps(_run_payload(outcome, picks), sort_keys=True, default=str))
    if outcome.status == "already_running":
        active = outcome.active_trade_date
        if active is not None and active != trade_date:
            if not as_json:
                typer.echo(f"another run is active for {active.isoformat()}", err=True)
            raise typer.Exit(RunExit.NOT_NOW)
        if not as_json:
            typer.echo(f"already running for {trade_date.isoformat()}")
        return
    summary = outcome.summary
    if outcome.status == "failed":
        if not as_json:
            typer.echo(
                f"failed {outcome.run_id} ({outcome.error_code}): {outcome.error_detail}",
                err=True,
            )
        raise typer.Exit(RunExit.FAILED)
    if as_json:
        return
    typer.echo(
        f"published {outcome.run_id} for {trade_date.isoformat()}: "
        f"scored {summary.get('tickers_scored', 0)}, excluded {summary.get('tickers_excluded', 0)}"
    )
    for item in summary.get("excluded", []):
        typer.echo(f"excluded {item['ticker']}: {item['reason']}")
    for pick in picks:
        typer.echo(
            f"{str(pick['side']).upper():<4} {pick['rank']} {pick['ticker']:<6} "
            f"{pick['display_score']} {pick['band']}"
        )
    if not picks:
        typer.echo("no picks today")
    typer.echo(DISCLAIMER)


@run_app.command("daily")
def run_daily(
    date_: Annotated[
        str | None,
        typer.Option("--date", help="Trade date YYYY-MM-DD (default: today in New York)."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the outcome as JSON.")] = False,
) -> None:
    """Run the daily pipeline inline and publish atomically (FR-901 to FR-906).

    Prints one line per state transition, then the summary. Exit 0 published or already
    running for the same date, 1 failed, 2 invalid date, 3 session not complete, another
    date's run active, or the database unreachable.
    """
    import signal  # noqa: PLC0415
    from datetime import date  # noqa: PLC0415
    from types import FrameType  # noqa: PLC0415

    from sqlalchemy.exc import SQLAlchemyError  # noqa: PLC0415

    from supertrends.data import db  # noqa: PLC0415
    from supertrends.data.providers.registry import (  # noqa: PLC0415
        fundamentals_provider,
        market_provider,
    )
    from supertrends.runs import orchestrator, service  # noqa: PLC0415
    from supertrends.runs.dates import TradeDateError, resolve_trade_date  # noqa: PLC0415
    from supertrends.runs.state import RunState  # noqa: PLC0415

    try:
        requested = date.fromisoformat(date_) if date_ else None
    except ValueError as exc:
        typer.echo(f"invalid --date: {date_}", err=True)
        raise typer.Exit(RunExit.USAGE) from exc
    try:
        trade_date = resolve_trade_date(requested)
    except TradeDateError as exc:
        typer.echo(f"{exc.code}: {exc}", err=True)
        raise typer.Exit(exc.exit_code) from exc
    settings = load_settings()
    try:
        cfg = load_scoring_config(Path(settings.scoring_config))
    except ConfigError as exc:
        typer.echo(f"invalid scoring config: {exc}", err=True)
        raise typer.Exit(RunExit.USAGE) from exc
    deps = orchestrator.RunDeps(
        market=market_provider(settings),
        fundamentals=fundamentals_provider(settings),
        config=cfg,
        queued_timeout_seconds=settings.queued_run_timeout_seconds,
    )

    def progress(run_id: str, state: RunState) -> None:
        if not as_json:
            typer.echo(f"{run_id} {state.value}")

    def on_sigterm(signum: int, frame: FrameType | None) -> None:
        raise orchestrator.RunTerminated

    previous = signal.signal(signal.SIGTERM, on_sigterm)
    engine = db.create_db_engine(settings)
    try:
        outcome = orchestrator.execute_run(
            engine, deps, trade_date=trade_date, trigger="cli", progress=progress
        )
        picks = (
            [
                {
                    "side": r.side,
                    "rank": r.rank,
                    "ticker": r.symbol,
                    "display_score": r.display_score,
                    "confidence": r.confidence,
                    "band": r.band,
                    "disclaimer": r.disclaimer,
                }
                for r in service.recommendations_for_run(engine, outcome.run_id)
            ]
            if outcome.status == "published" and outcome.run_id
            else []
        )
    except orchestrator.RunTerminated as exc:
        typer.echo("run terminated", err=True)
        raise typer.Exit(RunExit.FAILED) from exc
    except SQLAlchemyError as exc:
        typer.echo(f"database error: {type(exc).__name__}", err=True)
        raise typer.Exit(RunExit.NOT_NOW) from exc
    finally:
        signal.signal(signal.SIGTERM, previous)
        engine.dispose()
    _report_run(outcome, picks, trade_date, as_json=as_json)


def main() -> None:
    """Console script entry point."""
    app()
