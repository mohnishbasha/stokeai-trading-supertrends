# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Bearer-token auth for write endpoints (ARCHITECTURE 6.1 "Authentication", section 9)."""

from __future__ import annotations

import hmac
from typing import Annotated

import structlog
from fastapi import Depends, Header

from supertrends.api.deps import SettingsDep
from supertrends.api.problems import ProblemError

log = structlog.get_logger("supertrends.api.security")


def require_write_token(
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Allow the request only with `Authorization: Bearer <SUPERTRENDS_API_TOKEN>`.

    Compared with `hmac.compare_digest`. Missing or wrong token raises 401 with no detail
    about which part failed.
    """
    scheme, _, supplied = (authorization or "").partition(" ")
    expected = settings.api_token.get_secret_value().encode()
    ok = scheme.lower() == "bearer" and hmac.compare_digest(supplied.strip().encode(), expected)
    if not ok:
        log.warning("auth_failed", error_code="unauthorized")
        raise ProblemError(
            401,
            "unauthorized",
            "A valid bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


WriteToken = Depends(require_write_token)
