# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Provider call recording (ARCHITECTURE section 7.3, "Recording").

Every outbound provider call, including cache hits, is reported to a `CallRecorder`. Rows hold
the endpoint path template and non-secret parameters only, never an API key or a full URL.
"""

import threading
from dataclasses import dataclass
from typing import Protocol


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


class InMemoryCallRecorder:
    """Keeps rows in a list. Default recorder and the test double."""

    def __init__(self) -> None:
        self.calls: list[CallRecord] = []
        self._lock = threading.Lock()

    def record(self, call: CallRecord) -> None:
        with self._lock:
            self.calls.append(call)


def database_call_recorder() -> CallRecorder:
    """Recorder that writes `provider_calls` rows to Postgres.

    TODO(#16): S1-T06 adds the repository and wires this in once the S1-T01 table is merged.
    """
    msg = "database call recorder arrives with S1-T06 (#16)"
    raise NotImplementedError(msg)
