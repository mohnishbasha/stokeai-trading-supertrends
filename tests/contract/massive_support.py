# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Recorded-fixture transport and fake clock for the Massive adapter tests (no network)."""

import json
import re
from collections.abc import Callable
from pathlib import Path

import httpx

from supertrends.data.providers.massive import MassiveClient
from supertrends.data.providers.recording import InMemoryCallRecorder

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "providers" / "massive"
BASE_URL = "https://api.massive.com"
SECRET = "sk-test-SECRET-KEY-123456"  # noqa: S105 (fake key)

Handler = Callable[[httpx.Request], httpx.Response]


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def recorded_handler(request: httpx.Request) -> httpx.Response:
    """Serve the scrubbed fixtures; fails the test if the key leaves by query string."""
    assert request.headers["Authorization"] == f"Bearer {SECRET}"
    assert "apikey" not in request.url.query.decode().lower()
    path = request.url.path
    ticker = request.url.params.get("ticker") or request.url.params.get("tickers") or ""
    if m := re.match(r"/v2/aggs/ticker/([^/]+)/range/1/day/", path):
        name = "daily_AAA.json" if m[1] == "AAA" else "daily_empty.json"
    elif m := re.match(r"/v2/aggs/ticker/([^/]+)/range/5/minute/", path):
        name = "intraday_AAA.json" if m[1] == "AAA" else "daily_empty.json"
    elif m := re.match(r"/v2/aggs/grouped/locale/us/market/stocks/([\d-]+)$", path):
        name = f"grouped_{m[1]}.json"
        if not (FIXTURES / name).exists():
            name = "empty_results.json"
    elif path == "/stocks/v1/splits":
        name = "splits_AAA.json" if ticker == "AAA" else "empty_results.json"
    elif path == "/stocks/v1/dividends":
        name = "dividends_AAA.json" if ticker == "AAA" else "empty_results.json"
    elif path == "/stocks/financials/v1/income-statements":
        name = "financials_AAA.json" if ticker == "AAA" else "empty_results.json"
    elif m := re.match(r"/v3/reference/tickers/([^/]+)$", path):
        if m[1] != "AAA":
            return httpx.Response(404, json={"status": "NOT_FOUND"})
        name = "ticker_AAA.json"
    else:
        return httpx.Response(404, json={"status": "NOT_FOUND"})
    return httpx.Response(200, content=load(name), headers={"content-type": "application/json"})


class FakeClock:
    """Monotonic clock whose sleep advances time; records every sleep."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(
    handler: Handler = recorded_handler,
    *,
    key: str = SECRET,
    rate: int = 1000,
    clock: FakeClock | None = None,
    base_url: str = BASE_URL,
) -> tuple[MassiveClient, InMemoryCallRecorder, FakeClock]:
    clock = clock or FakeClock()
    recorder = InMemoryCallRecorder()
    client = MassiveClient(
        base_url=base_url,
        api_key=key,
        rate_per_min=rate,
        recorder=recorder,
        transport=httpx.MockTransport(handler),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        rng=lambda: 0.5,
    )
    return client, recorder, clock


def json_response(body: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(body).encode())
