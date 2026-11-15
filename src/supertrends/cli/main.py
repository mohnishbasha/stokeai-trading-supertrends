# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""`supertrends` entry point (ARCHITECTURE section 6, CLI).

Sprint 0 commands: --version, serve, healthcheck.
"""

from enum import IntEnum
from typing import Annotated

import httpx
import typer

from supertrends.settings import load_settings
from supertrends.version import LICENSE_NOTICE, get_commit, get_version, source_url

DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS = 3.0

app = typer.Typer(name="supertrends", no_args_is_help=True, add_completion=False)


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
    host, _, port = (bind or settings.bind).rpartition(":")
    uvicorn.run(
        "supertrends.api.app:create_app",
        factory=True,
        host=host,
        port=int(port),
        log_level=settings.effective_log_level,
        proxy_headers=False,
    )


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


def main() -> None:
    """Console script entry point."""
    app()
