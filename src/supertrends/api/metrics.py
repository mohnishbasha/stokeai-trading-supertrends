# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Process-local HTTP metrics (ARCHITECTURE 11.1). Labels never carry user-controlled values."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from supertrends.version import get_commit, get_version

_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)


class HttpMetrics:
    """Per-app registry holding request count, latency, and build info."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.requests = Counter(
            "supertrends_http_requests_total",
            "HTTP requests",
            ["method", "route", "status"],
            registry=self.registry,
        )
        self.duration = Histogram(
            "supertrends_http_request_duration_seconds",
            "HTTP request duration",
            ["method", "route"],
            buckets=_BUCKETS,
            registry=self.registry,
        )
        Gauge(
            "supertrends_build_info",
            "Build identity (always 1)",
            ["version", "commit"],
            registry=self.registry,
        ).labels(version=get_version(), commit=get_commit()).set(1)

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        """Record one finished request. `method` is clamped to a known verb."""
        verb = method if method in _METHODS else "OTHER"
        self.requests.labels(method=verb, route=route, status=str(status)).inc()
        self.duration.labels(method=verb, route=route).observe(seconds)


_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
