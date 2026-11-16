# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Domain errors. Every error raised by Super Trends code subclasses SuperTrendsError."""


class SuperTrendsError(Exception):
    """Base class for Super Trends domain errors."""


class ConfigError(SuperTrendsError):
    """Invalid scoring config or environment settings. The message names the offending key."""


class ProviderError(SuperTrendsError):
    """Base class for market data and fundamentals provider errors (ARCHITECTURE section 7.3).

    Messages never include an API key, a full URL with a query string, or a response body
    longer than 200 characters.
    """


class ProviderUnconfigured(ProviderError):  # noqa: N818 (name fixed by ARCHITECTURE 7.3)
    """No API key, or the vendor rejected the key (401 or 403)."""


class ProviderRateLimited(ProviderError):  # noqa: N818 (name fixed by ARCHITECTURE 7.3)
    """The vendor answered 429 after the retry budget was spent."""

    def __init__(self, message: str = "provider rate limited", retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ProviderUnavailable(ProviderError):  # noqa: N818 (name fixed by ARCHITECTURE 7.3)
    """5xx, timeout, or connection error after retries."""


class ProviderDataError(ProviderError):
    """Malformed or invalid payload, for example an OHLC row that violates its invariants."""


class CapabilityNotSupported(ProviderError):  # noqa: N818 (name fixed by ARCHITECTURE 7.3)
    """The method needs a capability the provider or plan lacks. Raised without network I/O."""


class IngestError(SuperTrendsError):
    """Ingestion cannot continue, for example a provider outage affecting every ticker."""

    def __init__(self, message: str, *, code: str = "ingest_failed") -> None:
        super().__init__(message)
        self.code = code
