# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Pure ASGI middleware: request ID, Host allowlist, metrics, access log, 500 handling."""

from __future__ import annotations

import re
import time
import uuid

import structlog
from starlette.routing import Mount
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from supertrends.api.metrics import HttpMetrics
from supertrends.api.problems import problem_response
from supertrends.settings import Settings

REQUEST_ID_HEADER = "x-request-id"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")
HOST_EXEMPT_PATHS = frozenset({"/healthz", "/readyz", "/metrics"})  # ADR-024

log = structlog.get_logger("supertrends.api")


def host_allowed(host_header: str, allowed: list[str]) -> bool:
    """Case-insensitive match of the Host header (port ignored) against the allowlist."""
    host = host_header.strip().lower()
    if host.startswith("["):  # IPv6 literal
        name = host[: host.find("]") + 1]
    else:
        name = host.rsplit(":", 1)[0] if ":" in host else host
    return name in {a.lower() for a in allowed}


def route_label(scope: Scope) -> str:
    """Route template for metrics and logs; never the raw path (bounded cardinality)."""
    route = scope.get("route")
    if route is None or isinstance(route, Mount):
        return "ui" if isinstance(route, Mount) else "unmatched"
    return str(getattr(route, "path", "unmatched"))


class ObservabilityMiddleware:
    """Request ID, Host check (ADR-024), metrics, `http_request` log, RFC 9457 for 500s."""

    def __init__(self, app: ASGIApp, *, settings: Settings, metrics: HttpMetrics) -> None:
        self.app = app
        self.settings = settings
        self.metrics = metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
        inbound = headers.get(REQUEST_ID_HEADER, "")
        request_id = inbound if _SAFE_REQUEST_ID.match(inbound) else uuid.uuid4().hex
        scope["supertrends.request_id"] = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        status = 500
        started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status, started
            if message["type"] == "http.response.start":
                status = message["status"]
                started = True
                message.setdefault("headers", []).append(
                    (REQUEST_ID_HEADER.encode(), request_id.encode())
                )
            await send(message)

        try:
            path = scope.get("path", "")
            if path not in HOST_EXEMPT_PATHS and not host_allowed(
                headers.get("host", ""), self.settings.allowed_hosts
            ):
                log.warning("host_rejected", error_code="misdirected-request")
                response = problem_response(
                    scope, 421, "misdirected-request", "The Host header is not allowed."
                )
                await response(scope, receive, send_wrapper)
            else:
                await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            log.error(
                "unhandled_error", error_code="internal", exc_type=type(exc).__name__, exc_info=True
            )
            if not started:
                response = problem_response(
                    scope, 500, "internal", "An internal error occurred. Quote the request ID."
                )
                await response(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - start
            route = route_label(scope)
            method = str(scope.get("method", ""))
            self.metrics.observe(method, route, status, elapsed)
            log.info(
                "http_request",
                method=method,
                route=route,
                status=status,
                duration_ms=round(elapsed * 1000, 2),
            )
            structlog.contextvars.clear_contextvars()
