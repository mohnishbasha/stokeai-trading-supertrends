# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""ULID identifiers for runs and recommendations (ARCHITECTURE section 5, `length(id) = 26`).

48-bit millisecond timestamp plus 80 random bits, Crockford base32. Lexicographic order follows
creation time, so `ORDER BY id` is creation order to the millisecond.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

__all__ = ["CROCKFORD", "new_ulid"]

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_TIME_CHARS = 10
_RANDOM_CHARS = 16


def _encode(value: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(out))


def new_ulid(now: datetime | None = None, randomness: int | None = None) -> str:
    """A 26-character ULID for `now` (default the current time) and 80 random bits."""
    moment = now or datetime.now(UTC)
    millis = int(moment.timestamp() * 1000)
    if not 0 <= millis < 1 << 48:
        msg = f"timestamp out of ULID range: {moment.isoformat()}"
        raise ValueError(msg)
    rand = secrets.randbits(80) if randomness is None else randomness
    if not 0 <= rand < 1 << 80:
        msg = "randomness must be an 80-bit non-negative integer"
        raise ValueError(msg)
    return _encode(millis, _TIME_CHARS) + _encode(rand, _RANDOM_CHARS)
