# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""The CI Postgres service container is reachable (wiring for the Sprint 1 storage tests).

Runs only when SUPERTRENDS_IT_DATABASE_URL is set (CI integration-tests job).
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlsplit

import pytest

URL = os.environ.get("SUPERTRENDS_IT_DATABASE_URL", "")


@pytest.mark.skipif(not URL, reason="set SUPERTRENDS_IT_DATABASE_URL to run")
def test_it_postgres_service_accepts_tcp_connections() -> None:
    parts = urlsplit(URL)
    with socket.create_connection((parts.hostname or "localhost", parts.port or 5432), timeout=5):
        pass
