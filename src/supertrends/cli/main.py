# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""`supertrends` entry point (ARCHITECTURE section 6, CLI).

Sprint 0 commands: --version, serve, healthcheck, config show | validate | export-schema.
Sprint 1 adds db migrate.
"""

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from enum import IntEnum
from pathlib import Path
from typing import Annotated

import httpx
import typer
import yaml
from sqlalchemy.orm import Session

from supertrends.errors import ConfigError
from supertrends.scoring.config import config_hash, json_schema, load_scoring_config
from supertrends.settings import load_settings
from supertrends.version import LICENSE_NOTICE, get_commit, get_version, source_url

DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS = 3.0
CONFIG_INVALID_EXIT = 2

app = typer.Typer(name="supertrends", no_args_is_help=True, add_completion=False)
config_app = typer.Typer(help="Show, validate, and export the scoring config.")
app.add_typer(config_app, name="config")
db_app = typer.Typer(help="Database operations (local mode only).")
app.add_typer(db_app, name="db")
watchlist_app = typer.Typer(help="Watchlist operations (local mode only).")
app.add_typer(watchlist_app, name="watchlist")


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


def main() -> None:
    """Console script entry point."""
    app()
