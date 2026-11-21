# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""The committed OpenAPI document (ADR-073): deterministic rendering of the app's schema.

`make openapi` writes it to docs/openapi.json; a unit test and a CI step fail on drift.
"""

from __future__ import annotations

import json

from supertrends.api.app import create_app
from supertrends.settings import Settings

__all__ = ["render_openapi"]


def render_openapi() -> str:
    """OpenAPI 3.1 JSON with sorted keys, two-space indent and a trailing newline."""
    app = create_app(settings=Settings(api_token="openapi"))  # noqa: S106
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
