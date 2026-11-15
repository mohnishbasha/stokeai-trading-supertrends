# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""FastAPI application factory.

Liveness, readiness (database reachable and migrations at head), Prometheus metrics, the
observability middleware, RFC 9457 problem responses, the /api/v1 router, and the built UI
bundle. Add API routes to `supertrends.api.router.api_router`.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TextIO

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.exc import SQLAlchemyError

from supertrends.api.deps import EngineDep
from supertrends.api.metrics import HttpMetrics
from supertrends.api.middleware import ObservabilityMiddleware
from supertrends.api.problems import ProblemError, install_problem_handlers
from supertrends.api.router import api_router
from supertrends.data import db
from supertrends.logs import configure_logging
from supertrends.settings import Settings, load_settings
from supertrends.version import get_commit, get_version

DEFAULT_UI_DIR = "ui/dist"
log = structlog.get_logger("supertrends.api")


def create_app(
    ui_dir: Path | None = None,
    *,
    settings: Settings | None = None,
    log_stream: TextIO | None = None,
) -> FastAPI:
    """Build the ASGI application.

    `settings` defaults to the environment (SUPERTRENDS_*). The UI bundle is served from
    ui_dir, or SUPERTRENDS_UI_DIR, when that directory exists.
    """
    settings = settings or load_settings()
    configure_logging(settings, stream=log_stream)
    metrics = HttpMetrics()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        engine = getattr(app.state, "engine", None)
        if engine is not None:
            engine.dispose()

    app = FastAPI(title="Super Trends Market Agent", version=get_version(), lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = None
    install_problem_handlers(app)
    app.add_middleware(ObservabilityMiddleware, settings=settings, metrics=metrics)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness. No database access."""
        return {"status": "ok", "version": get_version(), "commit": get_commit()}

    @app.get("/readyz")
    def readyz(engine: EngineDep) -> dict[str, str]:
        """Readiness: the database answers and migrations are at head, else 503."""
        try:
            current = db.database_revision(engine)
        except SQLAlchemyError as exc:
            log.warning("not_ready", reason="database_unreachable", exc_type=type(exc).__name__)
            raise _not_ready("database_unreachable", "The database is unreachable.") from None
        if current != db.head_revision():
            log.warning("not_ready", reason="migrations_behind")
            raise _not_ready("migrations_behind", "Database migrations are not at head.")
        return {"status": "ready"}

    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint(_request: Request) -> Response:
        """Prometheus text exposition."""
        return Response(generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)

    app.include_router(api_router)

    static = ui_dir or Path(os.environ.get("SUPERTRENDS_UI_DIR", DEFAULT_UI_DIR))
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="ui")

    return app


def _not_ready(reason: str, detail: str) -> ProblemError:
    return ProblemError(
        503, "not-ready", detail, title="Service not ready", extra={"reason": reason}
    )
