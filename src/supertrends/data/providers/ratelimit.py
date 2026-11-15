# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Token-bucket rate limiter with an injectable clock (ARCHITECTURE section 7.3)."""

import threading
import time
from collections.abc import Callable


class TokenBucket:
    """Allows `rate_per_min` calls per minute: a full bucket of that size, refilled evenly.

    `acquire` blocks (through the injected `sleep`) until a token is available and returns the
    seconds it waited. `waited_seconds` accumulates all waits for the run summary
    (`rate_limit_waits_seconds`).
    """

    def __init__(
        self,
        rate_per_min: int,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if rate_per_min <= 0:
            msg = "rate_per_min must be positive"
            raise ValueError(msg)
        self._capacity = float(rate_per_min)
        self._per_second = rate_per_min / 60.0
        self._monotonic = monotonic
        self._sleep = sleep
        self._tokens = self._capacity
        self._last = monotonic()
        self._lock = threading.Lock()
        self.waited_seconds = 0.0

    def _refill(self) -> None:
        now = self._monotonic()
        self._tokens = min(self._capacity, self._tokens + (now - self._last) * self._per_second)
        self._last = now

    def acquire(self) -> float:
        """Take one token, sleeping until one is available. Returns seconds waited."""
        waited = 0.0
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    self.waited_seconds += waited
                    return waited
                wait = (1.0 - self._tokens) / self._per_second
            self._sleep(wait)
            waited += wait
