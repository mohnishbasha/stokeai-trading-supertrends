# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Massive (formerly Polygon.io) REST adapter (ARCHITECTURE 7.6, ADR-009, ADR-035).

Every path lives in `ENDPOINTS` so a vendor change is one edit. The key travels only in the
`Authorization: Bearer` header; recorded rows, logs, and error messages hold path templates and
non-secret parameters, and any text taken from a vendor response is scrubbed of the key.

`MassiveClient` owns the HTTP session, the token bucket, retries with exponential backoff and full
jitter, the response cache, and call recording. `MassiveProvider` (market data) and
`MassiveFundamentals` share one client per (base URL, key, rate) so the bucket is process-wide.
Verified against the vendor documentation on 2026-11-15 (see ADR-009 and ADR-035).
"""

import json
import random
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any, Literal, cast
from urllib.parse import parse_qsl, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import httpx
import structlog

from supertrends.data.providers.base import (
    Bar,
    CorporateAction,
    EarningsDate,
    ForwardEstimate,
    ProviderCapabilities,
    ProviderHealth,
    ProviderStatus,
    QuarterlyFinancials,
    SymbolInfo,
    validate_bar,
)
from supertrends.data.providers.ratelimit import TokenBucket
from supertrends.data.providers.recording import CallRecord, CallRecorder, InMemoryCallRecorder
from supertrends.errors import (
    CapabilityNotSupported,
    ConfigError,
    ProviderDataError,
    ProviderRateLimited,
    ProviderUnavailable,
    ProviderUnconfigured,
)
from supertrends.settings import Settings

NAME = "massive"
NEW_YORK = ZoneInfo("America/New_York")
MAX_ATTEMPTS = 5
BACKOFF_BASE_SECONDS = 1.0
BACKOFF_CAP_SECONDS = 30.0
RETRY_AFTER_CAP_SECONDS = 120.0
_MAX_BODY_CHARS = 200
_HTTP_ERROR = 400
_HTTP_SERVER_ERROR = 500

# One table for every vendor path (ARCHITECTURE 7.6). Placeholders are path parameters.
ENDPOINTS: dict[str, str] = {
    "grouped_daily": "/v2/aggs/grouped/locale/us/market/stocks/{date}",
    "daily_bars": "/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}",
    "intraday_bars": "/v2/aggs/ticker/{symbol}/range/5/minute/{start}/{end}",
    "splits": "/stocks/v1/splits",
    "dividends": "/stocks/v1/dividends",
    "ticker": "/v3/reference/tickers/{symbol}",
    "income_statements": "/stocks/financials/v1/income-statements",
}

_log = structlog.get_logger(__name__)
_Params = Mapping[str, object]


def _scrub(text: str, key: str) -> str:
    """Remove the API key from vendor-supplied text."""
    return text.replace(key, "***") if key else text


class MassiveClient:
    """Rate-limited, retrying, caching, recording HTTP client for the Massive REST API."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        base_url: str,
        api_key: str,
        rate_per_min: int,
        recorder: CallRecorder | None = None,
        transport: httpx.BaseTransport | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        rng: Callable[[], float] = random.random,
    ) -> None:
        parts = urlsplit(base_url)
        if parts.scheme != "https" or not parts.hostname:
            msg = "SUPERTRENDS_MASSIVE_BASE_URL must be an https URL"
            raise ConfigError(msg)
        self._base = f"https://{parts.netloc}"
        self._host = parts.hostname
        self._key = api_key
        self.recorder: CallRecorder = recorder if recorder is not None else InMemoryCallRecorder()
        self.bucket = TokenBucket(rate_per_min, monotonic=monotonic, sleep=sleep)
        self._monotonic = monotonic
        self._sleep = sleep
        self._rng = rng
        self._cache: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._health: ProviderHealth = "ok" if api_key else "unconfigured"
        self._detail: str | None = None if api_key else "SUPERTRENDS_MASSIVE_API_KEY is not set"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.Client(
            base_url=self._base,
            headers=headers,
            transport=transport,
            timeout=httpx.Timeout(30.0, connect=5.0),
            follow_redirects=False,
        )

    def status(self) -> ProviderStatus:
        """Health from the last call; never touches the network."""
        return ProviderStatus(NAME, self._health, self._detail)

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def get_pages(
        self,
        endpoint: str,
        path: Mapping[str, str] | None = None,
        params: _Params | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield each response page, following `next_url` only on the configured host.

        `endpoint` is a path template from `ENDPOINTS`; `path` fills its placeholders. A 404
        yields nothing (unknown symbol).
        """
        if not self._key:
            raise ProviderUnconfigured("SUPERTRENDS_MASSIVE_API_KEY is not set")
        path = path or {}
        query = {
            k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in (params or {}).items()
        }
        recorded = {**path, **query}
        target = self._base + endpoint.format(**path)
        page = 1
        while True:
            shown = {**recorded, "page": str(page)} if page > 1 else recorded
            body = self._cached_request(endpoint, shown, target, query)
            if body is None:
                return
            yield body
            next_url = body.get("next_url")
            if not isinstance(next_url, str) or not next_url:
                return
            target, query = self._follow(next_url)
            page += 1

    def _follow(self, next_url: str) -> tuple[str, dict[str, str]]:
        parts = urlsplit(next_url)
        if parts.scheme != "https" or parts.hostname != self._host:
            msg = "pagination URL does not match the configured base URL host"
            raise ProviderDataError(msg)
        query = {k: v for k, v in parse_qsl(parts.query) if k.lower() != "apikey"}
        return urlunsplit(("https", parts.netloc, parts.path, "", "")), query

    def _cached_request(
        self, endpoint: str, recorded: dict[str, str], url: str, query: dict[str, str]
    ) -> dict[str, Any] | None:
        cache_key = (endpoint, tuple(sorted(recorded.items())))
        with self._lock:
            hit = self._cache.get(cache_key)
        if hit is not None:
            self._record(endpoint, recorded, 200, 0.0, cache_hit=True)
            return hit
        body = self._request_with_retry(endpoint, recorded, url, query)
        if body is not None:
            with self._lock:
                self._cache[cache_key] = body
        return body

    def _record(
        self,
        endpoint: str,
        params: dict[str, str],
        status: int | None,
        duration_ms: float,
        *,
        cache_hit: bool,
    ) -> None:
        row = CallRecord(NAME, endpoint, dict(params), status, duration_ms, cache_hit)
        self.recorder.record(row)

    def _request_with_retry(
        self, endpoint: str, recorded: dict[str, str], url: str, query: dict[str, str]
    ) -> dict[str, Any] | None:
        last_status: int | None = None
        retry_after: float | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self.bucket.acquire()
            started = self._monotonic()
            response: httpx.Response | None = None
            error_kind: str | None = None
            try:
                response = self._http.get(url, params=query)
            except httpx.HTTPError as exc:
                # Only the class name is kept: the exception text may echo the URL.
                error_kind = type(exc).__name__
            duration_ms = (self._monotonic() - started) * 1000.0
            status = response.status_code if response is not None else None
            self._record(endpoint, recorded, status, duration_ms, cache_hit=False)
            _log.info(
                "provider_call",
                provider=NAME,
                endpoint=endpoint,
                status=status,
                attempt=attempt,
                error=error_kind,
            )
            if response is not None and status is not None and status < _HTTP_ERROR:
                self._health, self._detail = "ok", None
                return self._parse(response)
            if status in (401, 403):
                self._health = "unconfigured"
                self._detail = "vendor rejected the key (401/403): key invalid or plan lacks access"
                raise ProviderUnconfigured(self._detail)
            if status == 404:
                return None
            if (
                response is not None
                and status is not None
                and status != 429
                and status < _HTTP_SERVER_ERROR
            ):
                snippet = _scrub(response.text[:_MAX_BODY_CHARS], self._key)
                msg = f"vendor rejected the request ({status}) for {endpoint}: {snippet}"
                raise ProviderDataError(msg)
            last_status = status
            retry_after = self._retry_after(response)
            if attempt < MAX_ATTEMPTS:
                self._sleep(self._delay(attempt, retry_after))
        if last_status == 429:
            self._health, self._detail = "degraded", "rate limited by vendor"
            msg = f"rate limited (429) for {endpoint} after {MAX_ATTEMPTS} attempts"
            raise ProviderRateLimited(msg, retry_after)
        self._health, self._detail = "unreachable", "vendor unavailable"
        what = f"status {last_status}" if last_status is not None else "transport error"
        msg = f"unavailable ({what}) for {endpoint} after {MAX_ATTEMPTS} attempts"
        raise ProviderUnavailable(msg)

    def _delay(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return min(retry_after, RETRY_AFTER_CAP_SECONDS)
        ceiling = min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * float(2 ** (attempt - 1)))
        return self._rng() * ceiling  # full jitter

    @staticmethod
    def _retry_after(response: httpx.Response | None) -> float | None:
        if response is None:
            return None
        try:
            value = float(response.headers["Retry-After"])
        except (KeyError, ValueError):
            return None
        return value if value >= 0 else None

    @staticmethod
    def _parse(response: httpx.Response) -> dict[str, Any]:
        try:
            body = json.loads(response.content)
        except ValueError:
            msg = "vendor returned a body that is not JSON"
            raise ProviderDataError(msg) from None
        if not isinstance(body, dict):
            msg = "vendor returned an unexpected JSON shape"
            raise ProviderDataError(msg)
        return cast("dict[str, Any]", body)


# ---------------------------------------------------------------- conversions


def _results(page: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = page.get("results") or []
    if not isinstance(rows, list):
        msg = "vendor 'results' is not a list"
        raise ProviderDataError(msg)
    return cast("list[Mapping[str, Any]]", rows)


def _bar(symbol: str, row: Mapping[str, Any], ts: datetime) -> Bar:
    try:
        vw = row.get("vw")
        bar = Bar(
            symbol,
            ts,
            float(row["o"]),
            float(row["h"]),
            float(row["l"]),
            float(row["c"]),
            int(row["v"]),
            float(vw) if vw is not None else None,
        )
    except (KeyError, TypeError, ValueError):
        msg = f"malformed aggregate row for {symbol}"
        raise ProviderDataError(msg) from None
    return validate_bar(bar)


def _ms_to_utc(row: Mapping[str, Any], symbol: str) -> datetime:
    try:
        return datetime.fromtimestamp(int(row["t"]) / 1000.0, tz=UTC)
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        msg = f"malformed timestamp for {symbol}"
        raise ProviderDataError(msg) from None


def _session_ts(session: date) -> datetime:
    return datetime(session.year, session.month, session.day, tzinfo=NEW_YORK)


def _parse_date(value: object, what: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        msg = f"malformed {what}"
        raise ProviderDataError(msg) from None


def _dedupe_sorted(bars: list[Bar]) -> list[Bar]:
    return list({b.ts: b for b in sorted(bars, key=lambda b: b.ts)}.values())


def _num(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(cast("float", value))
    except (TypeError, ValueError):
        msg = "non-numeric financial value"
        raise ProviderDataError(msg) from None


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or not denominator:
        return None
    return numerator / denominator


_ETF_TYPES = {"ETF", "ETN", "ETS", "ETV"}


class MassiveProvider:
    """MarketDataProvider backed by the Massive REST API."""

    name = NAME

    def __init__(self, client: MassiveClient, *, intraday: bool = True) -> None:
        self._client = client
        self.capabilities = ProviderCapabilities(
            intraday=intraday, trades=False, adjusted=True, grouped_daily=True, reference=True
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "MassiveProvider":
        return cls(shared_client(settings))

    def daily_bars(self, symbol: str, start: date, end: date) -> Sequence[Bar]:
        bars: list[Bar] = []
        params = {"adjusted": True, "sort": "asc", "limit": 50000}
        path = {"symbol": symbol, "start": start.isoformat(), "end": end.isoformat()}
        for page in self._client.get_pages(ENDPOINTS["daily_bars"], path, params):
            for row in _results(page):
                day = _ms_to_utc(row, symbol).astimezone(NEW_YORK).date()
                if start <= day <= end:
                    bars.append(_bar(symbol, row, _session_ts(day)))
        return _dedupe_sorted(bars)

    def grouped_daily(self, session: date) -> Sequence[Bar]:
        bars: list[Bar] = []
        for page in self._client.get_pages(
            ENDPOINTS["grouped_daily"], {"date": session.isoformat()}, {"adjusted": True}
        ):
            for row in _results(page):
                symbol = row.get("T")
                if not isinstance(symbol, str) or not symbol:
                    msg = "grouped row without a symbol"
                    raise ProviderDataError(msg)
                bars.append(_bar(symbol, row, _session_ts(session)))
        return sorted(bars, key=lambda b: b.symbol)

    def intraday_bars(
        self, symbol: str, start: date, end: date, minutes: Literal[5] = 5
    ) -> Sequence[Bar]:
        if not self.capabilities.intraday or minutes != 5:
            msg = "5-minute bars are not available on this provider or plan"
            raise CapabilityNotSupported(msg)
        bars: list[Bar] = []
        params = {"adjusted": True, "sort": "asc", "limit": 50000}
        path = {"symbol": symbol, "start": start.isoformat(), "end": end.isoformat()}
        for page in self._client.get_pages(ENDPOINTS["intraday_bars"], path, params):
            for row in _results(page):
                ts = _ms_to_utc(row, symbol)
                if start <= ts.astimezone(NEW_YORK).date() <= end:
                    bars.append(_bar(symbol, row, ts))
        return _dedupe_sorted(bars)

    def corporate_actions(self, symbol: str, start: date, end: date) -> Sequence[CorporateAction]:
        out: dict[tuple[date, str], CorporateAction] = {}
        splits = {
            "ticker": symbol,
            "limit": 1000,
            "execution_date.gte": start.isoformat(),
            "execution_date.lte": end.isoformat(),
        }
        for page in self._client.get_pages(ENDPOINTS["splits"], params=splits):
            for row in _results(page):
                try:
                    ex = _parse_date(row["execution_date"], "split date")
                    ratio = float(row["split_to"]) / float(row["split_from"])
                except (KeyError, TypeError, ValueError, ZeroDivisionError):
                    msg = f"malformed split row for {symbol}"
                    raise ProviderDataError(msg) from None
                if start <= ex <= end and ratio > 0:
                    out[(ex, "split")] = CorporateAction(symbol, ex, "split", ratio, None)
        dividends = {
            "ticker": symbol,
            "limit": 1000,
            "ex_dividend_date.gte": start.isoformat(),
            "ex_dividend_date.lte": end.isoformat(),
        }
        for page in self._client.get_pages(ENDPOINTS["dividends"], params=dividends):
            for row in _results(page):
                try:
                    ex = _parse_date(row["ex_dividend_date"], "dividend date")
                    amount = float(row["cash_amount"])
                except (KeyError, TypeError, ValueError):
                    msg = f"malformed dividend row for {symbol}"
                    raise ProviderDataError(msg) from None
                if start <= ex <= end and amount >= 0:
                    out[(ex, "dividend")] = CorporateAction(symbol, ex, "dividend", None, amount)
        return [out[k] for k in sorted(out)]

    def resolve_symbol(self, symbol: str) -> SymbolInfo | None:
        for page in self._client.get_pages(ENDPOINTS["ticker"], {"symbol": symbol}):
            row = page.get("results")
            if not isinstance(row, dict):
                return None
            kind = str(row.get("type", "")).upper()
            asset: Literal["stock", "etf", "index", "crypto"]
            if kind in _ETF_TYPES:
                asset = "etf"
            elif kind == "INDEX":
                asset = "index"
            elif kind == "CRYPTO":
                asset = "crypto"
            else:
                asset = "stock"
            name = row.get("name")
            label = name if isinstance(name, str) else None
            return SymbolInfo(symbol, label, asset, bool(row.get("active", True)))
        return None

    def trades(self, symbol: str, session: date) -> Sequence[object]:
        msg = "trades are not used in v1 (ADR-010)"
        raise CapabilityNotSupported(msg)

    def status(self) -> ProviderStatus:
        return self._client.status()


class MassiveFundamentals:
    """FundamentalsProvider backed by the Massive financials endpoints."""

    name = NAME
    supports_forward_estimates = False

    def __init__(self, client: MassiveClient) -> None:
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> "MassiveFundamentals":
        return cls(shared_client(settings))

    def quarterly_financials(self, symbol: str, since: date) -> Sequence[QuarterlyFinancials]:
        out: dict[date, QuarterlyFinancials] = {}
        params = {
            "tickers": symbol,
            "timeframe": "quarterly",
            "period_end.gte": since.isoformat(),
            "sort": "period_end.asc",
            "limit": 1000,
        }
        for page in self._client.get_pages(ENDPOINTS["income_statements"], params=params):
            for row in _results(page):
                try:
                    end = _parse_date(row["period_end"], "period end")
                    filed = _parse_date(row["filing_date"], "filing date")
                except KeyError:
                    msg = f"malformed financials row for {symbol}"
                    raise ProviderDataError(msg) from None
                if end < since:
                    continue
                revenue = _num(row.get("revenue"))
                out[end] = QuarterlyFinancials(
                    symbol,
                    end,
                    datetime(filed.year, filed.month, filed.day, tzinfo=UTC),
                    {
                        "revenue": revenue,
                        "eps_diluted": _num(row.get("diluted_earnings_per_share")),
                        "gross_margin": _ratio(_num(row.get("gross_profit")), revenue),
                        "operating_margin": _ratio(_num(row.get("operating_income")), revenue),
                        "fcf": None,  # needs the cash-flow endpoint (ADR-009 delta)
                        "net_debt": None,  # needs the balance-sheet endpoint (ADR-009 delta)
                        "shares": _num(row.get("diluted_shares_outstanding")),
                    },
                )
        return [out[k] for k in sorted(out)]

    def forward_estimates(self, symbol: str) -> Sequence[ForwardEstimate]:
        return []

    def earnings_dates(self, symbol: str, start: date, end: date) -> Sequence[EarningsDate]:
        msg = "Massive has no earnings calendar endpoint (verified 2026-11-15)"
        raise CapabilityNotSupported(msg)

    def status(self) -> ProviderStatus:
        return self._client.status()


_SHARED: dict[tuple[str, str, int], MassiveClient] = {}
_SHARED_LOCK = threading.Lock()


def shared_client(settings: Settings) -> MassiveClient:
    """One client (and so one token bucket and cache) per process for these settings."""
    key = (
        settings.massive_base_url,
        settings.massive_api_key.get_secret_value(),
        settings.provider_rate_per_min,
    )
    with _SHARED_LOCK:
        client = _SHARED.get(key)
        if client is None:
            client = MassiveClient(base_url=key[0], api_key=key[1], rate_per_min=key[2])
            _SHARED[key] = client
        return client


def reset_shared_clients() -> None:
    """Drop the shared clients (tests)."""
    with _SHARED_LOCK:
        _SHARED.clear()
