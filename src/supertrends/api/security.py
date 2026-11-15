# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Bearer-token protection for write endpoints (ARCHITECTURE 6.1 Authentication, ADR-015)."""

import hmac
from functools import lru_cache

from fastapi import Depends, HTTPException, Request

from supertrends.settings import Settings, load_settings

BEARER_PREFIX = "bearer "


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process settings, read once. Tests override this dependency."""
    return load_settings()


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401, detail="unauthorized", headers={"WWW-Authenticate": "Bearer"}
    )


def require_write_token(
    request: Request,
    settings: Settings = Depends(get_settings),  # noqa: B008 (FastAPI dependency style)
) -> None:
    """Require `Authorization: Bearer <SUPERTRENDS_API_TOKEN>`; compare in constant time."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith(BEARER_PREFIX):
        raise _unauthorized()
    presented = header[len(BEARER_PREFIX) :].strip().encode()
    expected = settings.api_token.get_secret_value().encode()
    if not expected or not hmac.compare_digest(presented, expected):
        raise _unauthorized()
