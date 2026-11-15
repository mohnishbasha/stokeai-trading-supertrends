# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""RFC 9457 problem responses (ARCHITECTURE 6.1 "Errors").

`detail` never carries a secret, a stack trace, or an upstream body.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_MEDIA_TYPE = "application/problem+json"
TYPE_PREFIX = "urn:supertrends:problem:"
_STATUS_SLUGS = {
    400: "bad-request",
    401: "unauthorized",
    404: "not-found",
    405: "method-not-allowed",
    409: "conflict",
    421: "misdirected-request",
    422: "validation-error",
    429: "rate-limited",
    500: "internal",
    503: "not-ready",
}


class ProblemError(Exception):
    """Raise from routes and dependencies to produce a specific problem response."""

    def __init__(  # noqa: PLR0913
        self,
        status: int,
        slug: str,
        detail: str,
        *,
        title: str | None = None,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.slug = slug
        self.detail = detail
        self.title = title
        self.headers = headers
        self.extra = extra or {}


def request_id_of(scope: Any) -> str:
    """The request ID the middleware stored on the ASGI scope ('' outside a request)."""
    return str(scope.get("supertrends.request_id", ""))


def problem_response(  # noqa: PLR0913
    scope: Any,
    status: int,
    slug: str,
    detail: str,
    *,
    title: str | None = None,
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build an `application/problem+json` response for the request in `scope`."""
    body: dict[str, Any] = {
        "type": f"{TYPE_PREFIX}{slug}",
        "title": title or HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "instance": str(scope.get("path", "")),
        "request_id": request_id_of(scope),
    }
    body.update(extra or {})
    return JSONResponse(body, status_code=status, headers=headers, media_type=PROBLEM_MEDIA_TYPE)


def install_problem_handlers(app: FastAPI) -> None:
    """Route HTTP, validation, and domain problem errors through problem+json."""

    @app.exception_handler(ProblemError)
    async def _problem(request: Request, exc: ProblemError) -> JSONResponse:
        return problem_response(
            request.scope,
            exc.status,
            exc.slug,
            exc.detail,
            title=exc.title,
            headers=exc.headers,
            extra=exc.extra,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        slug = _STATUS_SLUGS.get(exc.status_code, HTTPStatus(exc.status_code).phrase.lower())
        slug = slug.replace(" ", "-")
        detail = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
        return problem_response(
            request.scope, exc.status_code, slug, detail, headers=dict(exc.headers or {})
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": [str(p) for p in e["loc"]], "msg": str(e["msg"])} for e in exc.errors()]
        return problem_response(
            request.scope,
            422,
            "validation-error",
            "The request is invalid.",
            extra={"errors": errors},
        )
