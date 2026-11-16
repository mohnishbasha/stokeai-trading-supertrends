# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Token bucket respects calls per minute with a fake clock (TS-ING-010)."""

import pytest

from supertrends.data.providers.ratelimit import TokenBucket
from tests.contract.massive_support import FakeClock


def _bucket(rate: int, clock: FakeClock) -> TokenBucket:
    return TokenBucket(rate, monotonic=clock.monotonic, sleep=clock.sleep)


def test_unit_rate_limiter_allows_n_calls_then_blocks_the_next() -> None:
    clock = FakeClock()
    bucket = _bucket(5, clock)
    assert [bucket.acquire() for _ in range(5)] == [0.0] * 5
    assert clock.sleeps == []
    waited = bucket.acquire()
    assert waited == pytest.approx(12.0)  # one token every 60/5 seconds
    assert clock.sleeps == [pytest.approx(12.0)]
    assert bucket.waited_seconds == pytest.approx(12.0)


def test_unit_rate_limiter_never_exceeds_rate_over_a_minute() -> None:
    clock = FakeClock()
    bucket = _bucket(5, clock)
    start = clock.now
    for _ in range(15):
        bucket.acquire()
    # 5 burst, then 10 more at one per 12 seconds.
    assert clock.now - start == pytest.approx(120.0)


def test_unit_rate_limiter_refills_while_idle_but_caps_at_capacity() -> None:
    clock = FakeClock()
    bucket = _bucket(2, clock)
    bucket.acquire()
    bucket.acquire()
    clock.now += 3600
    assert bucket.acquire() == 0.0
    assert bucket.acquire() == 0.0
    assert bucket.acquire() > 0.0


def test_unit_rate_limiter_rejects_non_positive_rate() -> None:
    with pytest.raises(ValueError, match="positive"):
        TokenBucket(0)
