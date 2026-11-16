# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Shared FastAPI dependencies: settings, database engine, and session.

Tests override them with `app.dependency_overrides[get_settings]` or by passing `settings=`
to `create_app`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from supertrends.data import db
from supertrends.settings import Settings

CONNECT_TIMEOUT_SECONDS = "3"


def build_engine(settings: Settings) -> Engine:
    """Engine for the API with a short connect timeout so `/readyz` cannot hang."""
    url = make_url(db.normalize_database_url(settings.database_url.get_secret_value()))
    if url.get_backend_name() == "postgresql" and "connect_timeout" not in url.query:
        url = url.update_query_dict({"connect_timeout": CONNECT_TIMEOUT_SECONDS})
    return db.create_db_engine(url=url.render_as_string(hide_password=False))


def get_settings(request: Request) -> Settings:
    """The settings the app was built with."""
    settings: Settings = request.app.state.settings
    return settings


def get_engine(request: Request) -> Engine:
    """The app's engine, created on first use."""
    state = request.app.state
    if getattr(state, "engine", None) is None:
        state.engine = build_engine(state.settings)
    engine: Engine = state.engine
    return engine


def get_session(engine: Annotated[Engine, Depends(get_engine)]) -> Iterator[Session]:
    """A transactional session: commit on success, roll back on error."""
    with db.session_scope(engine) as session:
        yield session


SettingsDep = Annotated[Settings, Depends(get_settings)]
EngineDep = Annotated[Engine, Depends(get_engine)]
SessionDep = Annotated[Session, Depends(get_session)]
