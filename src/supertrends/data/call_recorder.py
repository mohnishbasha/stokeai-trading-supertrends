# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Database-backed provider call recorder (PRD FR-112, NFR-009; ARCHITECTURE section 5).

`CallRecord` and `CallRecorder` mirror `supertrends.data.providers.recording` from S1-T04
(PR #121) field for field, so `DbCallRecorder` satisfies the adapters' Protocol.
TODO(#16): once #121 lands, import `CallRecord` and `CallRecorder` from there and have
`database_call_recorder()` return `DbCallRecorder(get_engine())`.

`sanitize` removes anything secret shaped before a row is written: query strings are dropped
from the endpoint and parameters whose name looks like a credential are removed, so an API key
never reaches `provider_calls`. Each row is written in its own short transaction, so a rollback
of surrounding work does not erase the audit trail.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from supertrends.data.models import ProviderCall

_SECRET_NAME = re.compile(r"(api[-_]?key|token|secret|passw|authorization|auth|key)", re.I)
_BEARER = re.compile(r"\b(bearer|basic)\s+\S+", re.I)
REDACTED = "[redacted]"
TRANSPORT_ERROR = "error"


@dataclass(frozen=True)
class CallRecord:
    """One `provider_calls` row."""

    provider: str
    endpoint: str  # path template, for example /v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}
    params: dict[str, str]  # non-secret parameters, path parameters included
    status: int | None  # HTTP status; None for a transport error
    duration_ms: float
    cache_hit: bool
    run_id: str | None = None


class CallRecorder(Protocol):
    """Sink for provider call rows."""

    def record(self, call: CallRecord) -> None: ...


def sanitize(endpoint: str, params: Mapping[str, str]) -> tuple[str, dict[str, str]]:
    """Return the endpoint without a query string and params without credentials."""
    path = endpoint.split("?", 1)[0].split("#", 1)[0]
    clean = {
        str(name): _BEARER.sub(REDACTED, str(value))
        for name, value in params.items()
        if not _SECRET_NAME.search(str(name))
    }
    return path, clean


class DbCallRecorder:
    """Writes `provider_calls` rows, each in its own transaction."""

    def __init__(self, engine: Engine) -> None:
        self._factory: sessionmaker[Session] = sessionmaker(bind=engine, expire_on_commit=False)

    def record(self, call: CallRecord) -> None:
        path, params = sanitize(call.endpoint, call.params)
        with self._factory.begin() as session:
            session.add(
                ProviderCall(
                    run_id=call.run_id,
                    provider=call.provider,
                    endpoint=path,
                    params=params,
                    status=TRANSPORT_ERROR if call.status is None else str(call.status),
                    duration_ms=max(0, round(call.duration_ms)),
                    cache_hit=call.cache_hit,
                )
            )
