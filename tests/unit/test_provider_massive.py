# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Massive adapter: retries, rate limiting, caching, recording, secrets, pagination.

TS-ING-009 to TS-ING-015 and TS-ING-028. Vendor HTTP is a recorded-fixture MockTransport.
"""

from collections.abc import Callable, Iterator
from datetime import date

import httpx
import pytest
import structlog
from fastapi.testclient import TestClient

from supertrends.api.app import create_app
from supertrends.data.providers import registry
from supertrends.data.providers.massive import (
    ENDPOINTS,
    MassiveClient,
    MassiveFundamentals,
    MassiveProvider,
    reset_shared_clients,
)
from supertrends.data.providers.recording import database_call_recorder
from supertrends.errors import (
    CapabilityNotSupported,
    ConfigError,
    ProviderDataError,
    ProviderError,
    ProviderRateLimited,
    ProviderUnavailable,
    ProviderUnconfigured,
)
from supertrends.settings import Settings
from tests.contract.massive_support import (
    SECRET,
    json_response,
    load,
    make_client,
    recorded_handler,
)

START, END = date(2026, 1, 5), date(2026, 3, 27)
OK = {"status": "OK", "results": []}


def _sequence(
    *responses: httpx.Response,
) -> tuple[Callable[[httpx.Request], httpx.Response], list[httpx.Request]]:
    seen: list[httpx.Request] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return handler, seen


@pytest.fixture(autouse=True)
def _clean_shared() -> Iterator[None]:
    reset_shared_clients()
    yield
    reset_shared_clients()


def test_it_provider_massive_429_sequence_retried_then_succeeds() -> None:
    handler, seen = _sequence(
        httpx.Response(429),
        httpx.Response(429),
        httpx.Response(200, content=load("daily_AAA.json")),
    )
    client, recorder, clock = make_client(handler)
    bars = MassiveProvider(client).daily_bars("AAA", START, END)
    assert len(bars) > 0
    assert len(seen) == 3
    assert clock.sleeps == [0.5, 1.0]  # full jitter: rng 0.5 * (1 s, 2 s)
    assert [c.status for c in recorder.calls] == [429, 429, 200]


def test_it_provider_massive_retry_after_header_honored() -> None:
    handler, _ = _sequence(
        httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json=OK)
    )
    client, _, clock = make_client(handler)
    MassiveProvider(client).resolve_symbol("AAA")
    assert clock.sleeps == [7.0]


def test_it_provider_massive_5xx_exponential_backoff_with_jitter_bounded() -> None:
    handler, seen = _sequence(
        httpx.Response(503), httpx.Response(502), httpx.Response(200, json=OK)
    )
    client, _, clock = make_client(handler)
    assert MassiveProvider(client).daily_bars("AAA", START, END) == []
    assert len(seen) == 3
    assert clock.sleeps == [0.5, 1.0]


def test_it_provider_massive_backoff_is_capped_and_attempts_bounded() -> None:
    handler, seen = _sequence(httpx.Response(500))
    client, _, clock = make_client(handler)
    with pytest.raises(ProviderUnavailable):
        MassiveProvider(client).daily_bars("AAA", START, END)
    assert len(seen) == 5
    assert clock.sleeps == [0.5, 1.0, 2.0, 4.0]
    assert all(s <= 30.0 for s in clock.sleeps)


def test_it_provider_massive_429_exhausted_raises_rate_limited_with_retry_after() -> None:
    handler, seen = _sequence(httpx.Response(429, headers={"Retry-After": "3"}))
    client, _, _ = make_client(handler)
    with pytest.raises(ProviderRateLimited) as exc:
        MassiveProvider(client).daily_bars("AAA", START, END)
    assert len(seen) == 5
    assert exc.value.retry_after == 3.0
    assert client.status().health == "degraded"


def test_it_provider_massive_transport_error_retried_then_unavailable() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError(f"boom {request.url}")

    client, recorder, _ = make_client(handler)
    with pytest.raises(ProviderUnavailable) as exc:
        MassiveProvider(client).daily_bars("AAA", START, END)
    assert calls == 5
    assert "api.massive.com" not in str(exc.value)
    assert exc.value.__cause__ is None
    assert recorder.calls[0].status is None
    assert client.status().health == "unreachable"


@pytest.mark.parametrize("status", [401, 403])
def test_unit_provider_massive_rejected_key_is_unconfigured_without_retry(status: int) -> None:
    handler, seen = _sequence(httpx.Response(status))
    client, _, clock = make_client(handler)
    with pytest.raises(ProviderUnconfigured):
        MassiveProvider(client).daily_bars("AAA", START, END)
    assert len(seen) == 1
    assert clock.sleeps == []
    assert client.status().health == "unconfigured"


def test_unit_provider_massive_other_4xx_is_data_error_without_retry() -> None:
    handler, seen = _sequence(httpx.Response(400, text="bad request"))
    client, _, _ = make_client(handler)
    with pytest.raises(ProviderDataError, match="400"):
        MassiveProvider(client).daily_bars("AAA", START, END)
    assert len(seen) == 1


@pytest.mark.parametrize(
    "response",
    [httpx.Response(200, content=b"<html>"), httpx.Response(200, content=b"[1, 2]")],
)
def test_unit_provider_massive_malformed_body_is_data_error(response: httpx.Response) -> None:
    client, _, _ = make_client(lambda _r: response)
    with pytest.raises(ProviderDataError):
        MassiveProvider(client).daily_bars("AAA", START, END)


def test_unit_provider_massive_invalid_bar_is_data_error() -> None:
    bad = {"results": [{"t": 1767632400000, "o": 10, "h": 9, "l": 8, "c": 10, "v": 1}]}
    client, _, _ = make_client(lambda _r: json_response(bad))
    with pytest.raises(ProviderDataError):
        MassiveProvider(client).daily_bars("AAA", date(2026, 1, 1), date(2026, 1, 31))


def test_unit_provider_massive_malformed_row_is_data_error() -> None:
    client, _, _ = make_client(lambda _r: json_response({"results": [{"t": 1767632400000}]}))
    with pytest.raises(ProviderDataError, match="malformed"):
        MassiveProvider(client).daily_bars("AAA", date(2026, 1, 1), date(2026, 1, 31))


def test_it_provider_massive_response_cache_same_endpoint_params_one_call() -> None:
    handler, seen = _sequence(httpx.Response(200, content=load("daily_AAA.json")))
    client, recorder, _ = make_client(handler)
    provider = MassiveProvider(client)
    first = provider.daily_bars("AAA", START, END)
    second = provider.daily_bars("AAA", START, END)
    assert first == second
    assert len(seen) == 1
    assert [c.cache_hit for c in recorder.calls] == [False, True]
    provider.daily_bars("AAA", START, date(2026, 3, 26))  # different params: a new call
    assert len(seen) == 2
    client.clear_cache()
    provider.daily_bars("AAA", START, END)
    assert len(seen) == 3


def test_it_ingest_grouped_daily_one_call_returns_whole_market() -> None:
    handler, seen = _sequence(httpx.Response(200, content=load("grouped_2026-01-05.json")))
    client, recorder, _ = make_client(handler)
    bars = MassiveProvider(client).grouped_daily(START)
    assert [b.symbol for b in bars] == ["AAA", "BBB", "CCC"]
    assert {b.ts.date() for b in bars} == {START}
    assert len(seen) == 1
    assert seen[0].url.path.endswith("/2026-01-05")
    assert recorder.calls[0].endpoint == ENDPOINTS["grouped_daily"]


def test_unit_provider_massive_grouped_daily_holiday_is_empty() -> None:
    client, _, _ = make_client()
    assert list(MassiveProvider(client).grouped_daily(date(2026, 1, 1))) == []


def test_unit_provider_massive_bar_timestamps_are_new_york_sessions_and_utc_intraday() -> None:
    provider = MassiveProvider(make_client()[0])
    daily = provider.daily_bars("AAA", START, START)
    assert daily[0].ts.date() == START
    assert daily[0].ts.utcoffset() is not None
    assert daily[0].ts.tzname() == "EST"
    intraday = provider.intraday_bars("AAA", START, START)
    assert len(intraday) == 12
    assert intraday[0].ts.utcoffset().total_seconds() == 0  # type: ignore[union-attr]
    assert (intraday[0].ts.hour, intraday[0].ts.minute) == (14, 30)  # 09:30 EST


def test_unit_provider_massive_splits_and_dividends_map_fields() -> None:
    actions = MassiveProvider(make_client()[0]).corporate_actions("AAA", START, END)
    assert [(a.ex_date, a.kind, a.ratio, a.amount) for a in actions] == [
        (date(2026, 2, 10), "split", 4.0, None),
        (date(2026, 3, 12), "dividend", None, 0.25),
    ]


def test_unit_provider_massive_financials_map_metrics_and_known_at() -> None:
    rows = MassiveFundamentals(make_client()[0]).quarterly_financials("AAA", date(2025, 6, 1))
    assert [r.period_end for r in rows] == [
        date(2025, 6, 30),
        date(2025, 9, 30),
        date(2025, 12, 31),
    ]
    first = rows[0]
    assert first.known_at.date() == date(2025, 8, 1)
    assert first.metrics["gross_margin"] == pytest.approx(4e9 / 9.1e9)
    assert first.metrics["fcf"] is None
    assert first.metrics["shares"] == 1.5e10


def test_unit_provider_massive_pagination_follows_same_host_and_strips_key() -> None:
    page1 = {
        "results": [],
        "next_url": f"https://api.massive.com/stocks/v1/splits?cursor=abc&apiKey={SECRET}",
    }
    page2 = {
        "results": [
            {"ticker": "AAA", "execution_date": "2026-02-10", "split_from": 1, "split_to": 2}
        ]
    }
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/stocks/v1/splits":
            return json_response(page2 if request.url.params.get("cursor") else page1)
        return json_response(OK)

    client, recorder, _ = make_client(handler)
    actions = MassiveProvider(client).corporate_actions("AAA", START, END)
    assert [a.ratio for a in actions] == [2.0]
    assert "cursor=abc" in str(seen[1].url)
    assert all("apikey" not in str(r.url).lower() for r in seen)
    assert any(c.params.get("page") == "2" for c in recorder.calls)


def test_unit_provider_massive_pagination_to_other_host_is_refused() -> None:
    evil = {"results": [], "next_url": "https://evil.example/stocks/v1/splits?cursor=1"}
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return json_response(evil)

    client, _, _ = make_client(handler)
    with pytest.raises(ProviderDataError, match="host"):
        MassiveProvider(client).corporate_actions("AAA", START, END)
    assert len(seen) == 1


def test_unit_provider_massive_base_url_configurable_legacy_host_accepted() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return recorded_handler(request)

    for base in ("https://api.massive.com", "https://api.polygon.io"):
        client, _, _ = make_client(handler, base_url=base)
        MassiveProvider(client).resolve_symbol("AAA")
        assert seen[-1].url.host == base.removeprefix("https://")
    assert Settings().massive_base_url == "https://api.massive.com"
    with pytest.raises(ConfigError):
        make_client(base_url="http://api.massive.com")


def test_unit_provider_massive_unsupported_capabilities_raise_without_io() -> None:
    seen: list[httpx.Request] = []
    client, _, _ = make_client(lambda r: seen.append(r) or json_response(OK))  # type: ignore[func-returns-value]
    off = MassiveProvider(client, intraday=False)
    with pytest.raises(CapabilityNotSupported):
        off.intraday_bars("AAA", START, END)
    with pytest.raises(CapabilityNotSupported):
        off.trades("AAA", START)
    assert seen == []


# ------------------------------------------------------------------ secrets


def _assert_no_secret(*values: object) -> None:
    for v in values:
        assert SECRET not in str(v)
        assert SECRET not in repr(v)


def test_it_provider_calls_recorded_without_api_key_in_path_or_params() -> None:
    client, recorder, _ = make_client()
    provider = MassiveProvider(client)
    provider.daily_bars("AAA", START, END)
    provider.grouped_daily(START)
    provider.corporate_actions("AAA", START, END)
    provider.resolve_symbol("AAA")
    assert len(recorder.calls) >= 5
    for call in recorder.calls:
        _assert_no_secret(call)
        assert call.provider == "massive"
        assert call.endpoint in ENDPOINTS.values()  # templates, never concrete URLs
        assert "?" not in call.endpoint


def test_unit_provider_massive_key_never_in_logs_even_when_vendor_echoes_url() -> None:
    echo = f"error calling https://api.massive.com/v2/aggs?apiKey={SECRET}"
    handler, _ = _sequence(
        httpx.Response(500, text=echo), httpx.Response(200, content=load("daily_AAA.json"))
    )
    client, recorder, _ = make_client(handler)
    with structlog.testing.capture_logs() as logs:
        MassiveProvider(client).daily_bars("AAA", START, END)
    assert logs
    _assert_no_secret(logs, recorder.calls)


@pytest.mark.parametrize(
    ("status", "error"),
    [(500, ProviderUnavailable), (429, ProviderRateLimited), (400, ProviderDataError)],
)
def test_unit_provider_massive_key_never_in_exception_when_vendor_echoes_url(
    status: int, error: type[ProviderError]
) -> None:
    echo = f"see https://api.massive.com/x?apiKey={SECRET} Bearer {SECRET}"
    handler, _ = _sequence(httpx.Response(status, text=echo))
    client, _, _ = make_client(handler)
    with structlog.testing.capture_logs() as logs, pytest.raises(error) as exc:
        MassiveProvider(client).daily_bars("AAA", START, END)
    _assert_no_secret(exc.value, exc.value.args, logs, client.status())
    assert exc.value.__cause__ is None


def test_unit_provider_massive_key_not_in_client_or_provider_repr() -> None:
    client, _, _ = make_client()
    _assert_no_secret(MassiveProvider(client).status(), client.status())


def test_unit_provider_massive_malformed_status_detail_has_no_secret() -> None:
    handler, _ = _sequence(httpx.Response(403, text=SECRET))
    client, _, _ = make_client(handler)
    with pytest.raises(ProviderUnconfigured) as exc:
        MassiveProvider(client).resolve_symbol("AAA")
    _assert_no_secret(exc.value, client.status())


def test_unit_provider_massive_database_recorder_is_a_todo_for_s1_t06() -> None:
    with pytest.raises(NotImplementedError, match="S1-T06"):
        database_call_recorder()


# ------------------------------------------------------------- unconfigured


def test_unit_provider_massive_no_key_reports_unconfigured_and_makes_no_call() -> None:
    seen: list[httpx.Request] = []
    client, recorder, _ = make_client(lambda r: seen.append(r) or json_response(OK), key="")  # type: ignore[func-returns-value]
    provider = MassiveProvider(client)
    status = provider.status()
    assert status.health == "unconfigured"
    assert status.detail is not None
    assert MassiveFundamentals(client).status().health == "unconfigured"
    with pytest.raises(ProviderUnconfigured):
        provider.daily_bars("AAA", START, END)
    with pytest.raises(ProviderUnconfigured):
        provider.grouped_daily(START)
    assert seen == []
    assert recorder.calls == []


def test_unit_provider_massive_no_key_reports_unconfigured_app_starts_on_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SUPERTRENDS_MASSIVE_API_KEY", raising=False)
    # The registry builds the Massive provider with no key and it reports unconfigured.
    settings = Settings(market_provider="massive", massive_api_key="")  # type: ignore[arg-type]
    provider = registry.market_provider(settings)
    assert isinstance(provider, MassiveProvider)
    assert provider.status().health == "unconfigured"
    fundamentals = registry.fundamentals_provider(
        Settings(fundamentals_provider="massive", massive_api_key="")  # type: ignore[arg-type]
    )
    assert fundamentals.status().health == "unconfigured"
    # The app starts with the default (fixture) provider selection and no key.
    assert Settings().market_provider == "fixture"
    with TestClient(create_app()) as http:
        assert http.get("/healthz").status_code == 200
    try:
        fixture = registry.market_provider(Settings())
    except ConfigError:
        pytest.skip("fixture provider arrives with S1-T03")
    assert fixture.status().health != "unconfigured"


def test_unit_provider_massive_shared_client_is_process_wide_per_settings() -> None:
    settings = Settings(massive_api_key=SECRET, provider_rate_per_min=7)  # type: ignore[arg-type]
    a = MassiveProvider.from_settings(settings)
    b = MassiveFundamentals.from_settings(settings)
    assert a._client is b._client
    assert isinstance(a._client, MassiveClient)
