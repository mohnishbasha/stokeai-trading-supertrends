# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""FastAPI application factory.

Sprint 0 skeleton: liveness, readiness, and the built UI bundle. The database readiness
check, the Host allowlist, and the /api/v1 routes arrive with S1-T08.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from supertrends.version import get_commit, get_version

DEFAULT_UI_DIR = "ui/dist"


def create_app(ui_dir: Path | None = None) -> FastAPI:
    """Build the ASGI application.

    The UI bundle is served from ui_dir, or SUPERTRENDS_UI_DIR, when that directory exists.
    """
    app = FastAPI(title="Super Trends Market Agent", version=get_version())

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness. No database access."""
        return {"status": "ok", "version": get_version(), "commit": get_commit()}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        """Readiness. TODO(#18): check the database and migrations."""
        return {"status": "ready"}

    static = ui_dir or Path(os.environ.get("SUPERTRENDS_UI_DIR", DEFAULT_UI_DIR))
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="ui")

    return app
