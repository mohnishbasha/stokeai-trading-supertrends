# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Alternate market data provider: Alpaca Market Data (ARCHITECTURE section 7.7, ADR-032).

Implements `MarketDataProvider` over the Alpaca historical market data REST API
(endpoints verified against the vendor docs on 2026-11-15, see ADR-032).

* Authentication is by header only (`APCA-API-KEY-ID` and `APCA-API-SECRET-KEY`). Alpaca uses a
  key pair, so `SUPERTRENDS_ALTERNATE_API_KEY` holds `KEY_ID:SECRET`. The secret is never put in
  a URL, a log line, an error message, or `repr`.
* The base URL comes only from settings (`SUPERTRENDS_ALTERNATE_BASE_URL`, default
  `https://data.alpaca.markets`); pagination uses the `page_token` query parameter, so no URL
  taken from a response is ever followed.
* Daily bars are requested with `adjustment=all` (split and dividend adjusted). Intraday bars are
  5-minute bars restricted to the regular session (09:30 to 16:00 America/New_York). The free
  plan serves the IEX feed only (`feed=iex`), whose volume is a fraction of consolidated
  volume; a paid plan can set `feed="sip"`.
* There is no whole-market daily endpoint and no tick-trade access here, so `grouped_daily` and
  `trades` raise `CapabilityNotSupported` without network I/O.

Retry: 429, 5xx, and transport errors are retried with exponential backoff and full jitter (base
1 s, cap 30 s, 5 attempts, `Retry-After` honored) through an injectable `sleep`.

Consolidation note: the retry loop here is self-contained because no shared HTTP helper exists
yet. When the Massive adapter (S1-T04) lands, fold both into one shared helper that also adds the
token-bucket rate limit, per-run response cache, and `provider_calls` recording of section 7.3.
"""

import math
import random
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from typing import Any, Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from supertrends.data.providers.base import (
    Bar,
    CorporateAction,
    ProviderCapabilities,
    ProviderStatus,
    SymbolInfo,
    validate_bar,
)
from supertrends.errors import (
    CapabilityNotSupported,
    ConfigError,
    ProviderDataError,
    ProviderRateLimited,
    ProviderUnavailable,
    ProviderUnconfigured,
)
from supertrends.settings import Settings

NY = ZoneInfo("America/New_York")
DEFAULT_BASE_URL = "https://data.alpaca.markets"
_BARS_PATH = "/v2/stocks/bars"
_ACTIONS_PATH = "/v1/corporate-actions"
_PAGE_LIMIT = 10_000
_ACTIONS_LIMIT = 1_000
_MAX_PAGES = 200
_MAX_ATTEMPTS = 5
_BACKOFF_BASE = 1.0
_BACKOFF_CAP = 30.0
_SESSION_OPEN = dtime(9, 30)
_SESSION_CLOSE = dtime(16, 0)

Json = Mapping[str, Any]


def _utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(raw: object) -> datetime:
    if not isinstance(raw, str):
        raise ProviderDataError("bar timestamp is missing or not a string")
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ProviderDataError("bar timestamp is not ISO 8601") from exc
    if ts.tzinfo is None:
        raise ProviderDataError("bar timestamp has no timezone")
    return ts.astimezone(UTC)


def _num(row: Json, key: str) -> float:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ProviderDataError(f"bar field {key!r} is missing or not a number")
    if not math.isfinite(value):
        raise ProviderDataError(f"bar field {key!r} is not finite")
    return float(value)


class AlternateProvider:
    """Alpaca Market Data adapter. Build with `from_settings`."""

    name = "alternate"

    def __init__(  # noqa: PLR0913 (injectable seams for tests)
        self,
        api_key: str,
        base_url: str | None = None,
        *,
        feed: Literal["iex", "sip"] = "iex",
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
        today: Callable[[], date] | None = None,
        max_attempts: int = _MAX_ATTEMPTS,
    ) -> None:
        self._today = today or (lambda: datetime.now(NY).date())
        self._key_id, self._secret = self._split_key(api_key)
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        if urlsplit(self._base_url).scheme not in ("http", "https"):
            raise ConfigError("SUPERTRENDS_ALTERNATE_BASE_URL must be an http(s) URL")
        self._feed = feed
        self._sleep = sleep
        self._jitter = jitter
        self._max_attempts = max(1, max_attempts)
        self._client = httpx.Client(
            base_url=self._base_url,
            transport=transport,
            timeout=httpx.Timeout(30.0, connect=5.0),
        )
        self.capabilities = ProviderCapabilities(
            intraday=True,
            trades=False,
            adjusted=True,
            grouped_daily=False,
            reference=True,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "AlternateProvider":
        """Build from SUPERTRENDS_ALTERNATE_API_KEY and SUPERTRENDS_ALTERNATE_BASE_URL."""
        return cls(
            settings.alternate_api_key.get_secret_value(),
            settings.alternate_base_url or None,
        )

    def __repr__(self) -> str:
        return f"AlternateProvider(base_url={self._base_url!r}, configured={self._configured})"

    @staticmethod
    def _split_key(api_key: str) -> tuple[str, str]:
        key_id, sep, secret = api_key.strip().partition(":")
        if not sep or not key_id or not secret:
            return "", ""
        return key_id, secret

    @property
    def _configured(self) -> bool:
        return bool(self._key_id and self._secret)

    # ------------------------------------------------------------------ HTTP

    def _require_key(self) -> None:
        if not self._configured:
            raise ProviderUnconfigured(
                "alternate provider has no usable API key "
                "(set SUPERTRENDS_ALTERNATE_API_KEY to KEY_ID:SECRET)"
            )

    def _backoff(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return min(max(retry_after, 0.0), _BACKOFF_CAP)
        return float(self._jitter() * min(_BACKOFF_CAP, _BACKOFF_BASE * 2.0**attempt))

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        try:
            return float(raw) if raw is not None else None
        except ValueError:
            return None

    def _get(self, path: str, params: Mapping[str, str | int]) -> Json | None:
        """GET with auth headers and retry. Returns None on 404, else the JSON object."""
        self._require_key()
        headers = {"APCA-API-KEY-ID": self._key_id, "APCA-API-SECRET-KEY": self._secret}
        last_retry_after: float | None = None
        rate_limited = False
        for attempt in range(self._max_attempts):
            try:
                response = self._client.get(path, params=dict(params), headers=headers)
            except httpx.HTTPError as exc:
                rate_limited = False
                failure = type(exc).__name__
            else:
                status = response.status_code
                if status == 404:
                    return None
                if status in (401, 403):
                    raise ProviderUnconfigured(
                        f"alternate provider rejected the API key ({status})"
                    )
                if status == 429 or status >= 500:
                    rate_limited = status == 429
                    last_retry_after = self._retry_after(response)
                    failure = f"HTTP {status}"
                elif status >= 400:
                    raise ProviderDataError(f"alternate provider returned HTTP {status} for {path}")
                else:
                    return self._json(response, path)
            if attempt + 1 < self._max_attempts:
                self._sleep(self._backoff(attempt, last_retry_after))
        if rate_limited:
            raise ProviderRateLimited(
                f"alternate provider rate limited {path}", retry_after=last_retry_after
            )
        raise ProviderUnavailable(f"alternate provider unavailable for {path}: {failure}")

    @staticmethod
    def _json(response: httpx.Response, path: str) -> Json:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderDataError(f"alternate provider sent invalid JSON for {path}") from exc
        if not isinstance(payload, dict):
            raise ProviderDataError(f"alternate provider sent an unexpected payload for {path}")
        return payload

    # ------------------------------------------------------------------ bars

    def _fetch_bars(
        self, symbol: str, timeframe: str, start: date, end: date, *, adjusted: bool
    ) -> list[Json]:
        params: dict[str, str | int] = {
            "symbols": symbol,
            "timeframe": timeframe,
            "start": _utc(datetime.combine(start, dtime.min, NY)),
            "end": _utc(datetime.combine(end + timedelta(days=1), dtime.min, NY)),
            "limit": _PAGE_LIMIT,
            "sort": "asc",
            "feed": self._feed,
        }
        if adjusted:
            params["adjustment"] = "all"
        rows: list[Json] = []
        for _ in range(_MAX_PAGES):
            payload = self._get(_BARS_PATH, params)
            if payload is None:
                return rows
            by_symbol = payload.get("bars")
            if by_symbol is None:
                by_symbol = {}
            if not isinstance(by_symbol, dict):
                raise ProviderDataError("alternate provider sent a malformed bars map")
            page = by_symbol.get(symbol) or []
            if not isinstance(page, list) or not all(isinstance(r, dict) for r in page):
                raise ProviderDataError("alternate provider sent a malformed bars list")
            rows.extend(page)
            token = payload.get("next_page_token")
            if not token:
                return rows
            if not isinstance(token, str):
                raise ProviderDataError("alternate provider sent a malformed page token")
            params = {**params, "page_token": token}
        raise ProviderDataError("alternate provider pagination did not terminate")

    @staticmethod
    def _to_bar(symbol: str, ts: datetime, row: Json) -> Bar:
        volume = _num(row, "v")
        vwap = row.get("vw")
        return validate_bar(
            Bar(
                symbol=symbol,
                ts=ts,
                open=_num(row, "o"),
                high=_num(row, "h"),
                low=_num(row, "l"),
                close=_num(row, "c"),
                volume=int(volume),
                vwap=float(vwap) if isinstance(vwap, int | float) and math.isfinite(vwap) else None,
            )
        )

    @staticmethod
    def _dedupe(bars: Sequence[Bar]) -> list[Bar]:
        return sorted({b.ts: b for b in bars}.values(), key=lambda b: b.ts)

    def daily_bars(self, symbol: str, start: date, end: date) -> Sequence[Bar]:
        """Adjusted daily bars; `ts` is the session date at 00:00 America/New_York."""
        self._require_key()
        if end < start:
            return []
        bars: list[Bar] = []
        for row in self._fetch_bars(symbol, "1Day", start, end, adjusted=True):
            session = _parse_ts(row.get("t")).astimezone(NY).date()
            if start <= session <= end:
                bars.append(self._to_bar(symbol, datetime.combine(session, dtime.min, NY), row))
        return self._dedupe(bars)

    def grouped_daily(self, session: date) -> Sequence[Bar]:
        """Not supported: the vendor has no whole-market daily endpoint."""
        raise CapabilityNotSupported("alternate provider has no grouped daily endpoint")

    def intraday_bars(
        self, symbol: str, start: date, end: date, minutes: Literal[5] = 5
    ) -> Sequence[Bar]:
        """Regular-session 5-minute bars; `ts` is the bar start in UTC."""
        if minutes != 5:
            raise CapabilityNotSupported("alternate provider supports 5-minute bars only")
        self._require_key()
        if end < start:
            return []
        bars: list[Bar] = []
        for row in self._fetch_bars(symbol, f"{minutes}Min", start, end, adjusted=True):
            ts = _parse_ts(row.get("t"))
            local = ts.astimezone(NY)
            if not (start <= local.date() <= end):
                continue
            if not (_SESSION_OPEN <= local.time() < _SESSION_CLOSE):
                continue
            bars.append(self._to_bar(symbol, ts, row))
        return self._dedupe(bars)

    def trades(self, symbol: str, session: date) -> Sequence[object]:
        """Not supported: tick trades are unused in v1."""
        raise CapabilityNotSupported("alternate provider does not expose trades")

    # ------------------------------------------------------- reference data

    def corporate_actions(self, symbol: str, start: date, end: date) -> Sequence[CorporateAction]:
        """Splits (ratio new/old shares) and cash dividends with ex-dates in [start, end]."""
        self._require_key()
        if end < start:
            return []
        params: dict[str, str | int] = {
            "symbols": symbol,
            "types": "forward_split,reverse_split,cash_dividend",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": _ACTIONS_LIMIT,
            "sort": "asc",
        }
        splits: dict[date, CorporateAction] = {}
        dividends: dict[date, float] = {}
        for _ in range(_MAX_PAGES):
            payload = self._get(_ACTIONS_PATH, params)
            if payload is None:
                break
            groups = payload.get("corporate_actions") or {}
            if not isinstance(groups, dict):
                raise ProviderDataError("alternate provider sent malformed corporate actions")
            for key in ("forward_splits", "reverse_splits"):
                for row in self._rows(groups, key):
                    ex = self._ex_date(row)
                    if row.get("symbol") != symbol or not start <= ex <= end:
                        continue
                    new, old = _num(row, "new_rate"), _num(row, "old_rate")
                    if new <= 0 or old <= 0:
                        raise ProviderDataError("split rate is not positive")
                    splits.setdefault(ex, CorporateAction(symbol, ex, "split", new / old, None))
            for row in self._rows(groups, "cash_dividends"):
                ex = self._ex_date(row)
                if row.get("symbol") != symbol or not start <= ex <= end:
                    continue
                rate = _num(row, "rate")
                if rate < 0:
                    raise ProviderDataError("dividend rate is negative")
                dividends[ex] = dividends.get(ex, 0.0) + rate
            token = payload.get("next_page_token")
            if not token or not isinstance(token, str):
                break
            params = {**params, "page_token": token}
        out = list(splits.values())
        out.extend(
            CorporateAction(symbol, d, "dividend", None, amt) for d, amt in dividends.items()
        )
        return sorted(out, key=lambda a: (a.ex_date, a.kind))

    @staticmethod
    def _rows(groups: Json, key: str) -> list[Json]:
        rows = groups.get(key) or []
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ProviderDataError(f"alternate provider sent malformed {key}")
        return rows

    @staticmethod
    def _ex_date(row: Json) -> date:
        raw = row.get("ex_date")
        try:
            return date.fromisoformat(raw) if isinstance(raw, str) else _bad_date()
        except ValueError as exc:
            raise ProviderDataError("corporate action ex_date is not a date") from exc

    def resolve_symbol(self, symbol: str) -> SymbolInfo | None:
        """Known when the vendor has a bar in the last 14 days; None otherwise.

        The market data API has no reference endpoint (the asset catalog lives on the trading
        API host), and nothing here distinguishes an ETF from a stock, so `type` is "stock" and
        `name` is None.
        """
        self._require_key()
        today = self._today()
        rows = self._fetch_bars(symbol, "1Day", today - timedelta(days=14), today, adjusted=False)
        if not rows:
            return None
        return SymbolInfo(symbol=symbol, name=None, type="stock", active=True)

    # ---------------------------------------------------------------- status

    def status(self) -> ProviderStatus:
        """Health from one cheap probe. The detail never contains a secret."""
        if not self._configured:
            return ProviderStatus(self.name, "unconfigured", "no API key configured")
        today = self._today()
        try:
            self._fetch_bars("SPY", "1Day", today - timedelta(days=7), today, adjusted=False)
        except ProviderUnconfigured:
            return ProviderStatus(self.name, "unconfigured", "vendor rejected the API key")
        except ProviderRateLimited:
            return ProviderStatus(self.name, "degraded", "rate limited")
        except ProviderUnavailable:
            return ProviderStatus(self.name, "unreachable", "vendor unreachable")
        except ProviderDataError:
            return ProviderStatus(self.name, "degraded", "unexpected vendor response")
        return ProviderStatus(self.name, "ok", None)


def _bad_date() -> date:
    raise ProviderDataError("corporate action ex_date is missing")
