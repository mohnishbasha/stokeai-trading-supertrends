# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Generators and checks for the no-look-ahead harness (TEST_PLAN section 6).

`make_bundle` builds a valid OHLCV bundle (low <= open, close <= high, positive volume) from a
seed with numpy, including gaps, zero-range bars and exchange holidays (weeks with fewer than
five sessions). 5-minute bars exist from session `intraday_from` on, 78 per session, so a cut at
or after `intraday_from + 8` keeps the flow estimator on its intraday path. The `bundles`
strategy draws only the generator parameters (seed, length, volatility, gap and zero-range
rates): hypothesis shrinks those, which is far faster than drawing 3000 floats per example.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from hypothesis import strategies as st

from supertrends.indicators.registry import Bundle, Entry, canonical

BARS_PER_SESSION = 78  # 09:30 to 16:00 in 5-minute bars
OPEN_MINUTE = 9 * 60 + 30
TOL = 1e-12
FIXED_FIRST_CUT = 250
INTRADAY_FROM = 200


def make_bundle(
    seed: int,
    n: int,
    sigma: float = 0.015,
    p_gap: float = 0.05,
    p_flat: float = 0.03,
    intraday_from: int | None = INTRADAY_FROM,
    start_day: int = 19_000,
) -> Bundle:
    """A valid synthetic bundle of `n` sessions (see the module docstring)."""
    rng = np.random.default_rng(seed)
    candidates = np.arange(start_day, start_day + 2 * n + 30)
    weekday = (candidates + 3) % 7 < 5  # 1970-01-01 was a Thursday
    keep = weekday & (rng.random(len(candidates)) > 0.03)
    days = candidates[keep][:n]
    dates = days.astype("datetime64[D]")

    ret = rng.normal(0.0, sigma, n)
    gaps = np.where(
        rng.random(n) < p_gap, rng.normal(0.0, 4 * sigma, n), rng.normal(0.0, sigma / 3, n)
    )
    close = np.empty(n)
    open_ = np.empty(n)
    prev = 100.0 * float(np.exp(rng.normal(0.0, 1.0)))
    for i in range(n):
        open_[i] = prev * float(np.exp(gaps[i]))
        close[i] = open_[i] * float(np.exp(ret[i]))
        prev = close[i]
    up = rng.random(n) * sigma
    down = rng.random(n) * sigma
    high = np.maximum(open_, close) * (1.0 + up)
    low = np.minimum(open_, close) * (1.0 - down)
    flat = rng.random(n) < p_flat
    high = np.where(flat, close, high)
    low = np.where(flat, close, low)
    open_ = np.where(flat, close, open_)
    volume = np.maximum(1.0, np.round(1e6 * np.exp(rng.normal(0.0, 0.5, n))))

    if intraday_from is None or intraday_from >= n:
        return Bundle(
            dates,
            open_,
            high,
            low,
            close,
            volume,
            np.zeros(0, dtype=np.int64),
            np.zeros(0, dtype="datetime64[m]"),
            np.zeros(0),
            np.zeros(0),
            np.zeros(0),
            np.zeros(0),
        )
    s = np.arange(intraday_from, n)
    k = BARS_PER_SESSION
    path = low[s, None] + (high[s] - low[s])[:, None] * rng.random((len(s), k + 1))
    path[:, 0] = open_[s]
    path[:, -1] = close[s]
    o, c = path[:, :-1], path[:, 1:]
    hi = np.maximum(o, c)
    lo = np.minimum(o, c)
    hi = hi + (high[s, None] - hi) * rng.random(hi.shape)
    lo = lo - (lo - low[s, None]) * rng.random(lo.shape)
    vol = np.maximum(1.0, np.round(volume[s, None] / k * (0.5 + rng.random((len(s), k)))))
    minutes = dates[s].astype("datetime64[m]")[:, None] + (OPEN_MINUTE + 5 * np.arange(k)).astype(
        "timedelta64[m]"
    )
    return Bundle(
        dates,
        open_,
        high,
        low,
        close,
        volume,
        np.repeat(s, k).astype(np.int64),
        minutes.ravel(),
        hi.ravel(),
        lo.ravel(),
        c.ravel().copy(),
        vol.ravel(),
    )


@st.composite
def bundles(draw: st.DrawFn, *, min_len: int = 300, max_len: int = 700) -> Bundle:
    """Hypothesis strategy: a valid bundle of 300 to 700 sessions."""
    return make_bundle(
        seed=draw(st.integers(0, 2**32 - 1)),
        n=draw(st.integers(min_len, max_len)),
        sigma=draw(st.sampled_from([0.002, 0.01, 0.02, 0.05])),
        p_gap=draw(st.sampled_from([0.0, 0.05, 0.3])),
        p_flat=draw(st.sampled_from([0.0, 0.03, 0.5])),
    )


def _differs(a: object, b: object, path: str) -> str | None:  # noqa: PLR0911
    """First difference between two canonical structures (floats within TOL), or None."""
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return f"{path}: keys differ"
        for key in a:
            found = _differs(a[key], b[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            found = _differs(x, y, f"{path}[{i}]")
            if found:
                return found
        return None
    if isinstance(a, float) and isinstance(b, float):
        return None if abs(a - b) <= TOL * (1.0 + abs(a)) else f"{path}: {a!r} != {b!r}"
    return None if a == b and type(a) is type(b) else f"{path}: {a!r} != {b!r}"


def _same_arrays(a: np.ndarray, b: np.ndarray, count: int) -> bool:
    """NaN positions equal and finite values within TOL over the first `count` entries."""
    x, y = a[:count], b[:count]
    if not np.array_equal(np.isnan(x), np.isnan(y)):
        return False
    both = ~np.isnan(x)
    return bool(np.all(np.abs(x[both] - y[both]) <= TOL * (1.0 + np.abs(x[both]))))


def check_entry(
    entry: Entry, bundle: Bundle, cuts: Iterable[int], others: dict[int, Bundle]
) -> list[str]:
    """Violations of truncation and perturbation invariance for one entry.

    `cuts` are numbers of bars kept (the spec's `t`). `others[m]` is a bundle whose bars after
    `m` replace the real ones for the perturbation check (only cuts present in `others` get it).
    """
    found: list[str] = []
    full = entry.series(bundle) if entry.series else None
    for m in cuts:
        keep = m - entry.confirm_lag
        variants = {"truncation": bundle.head(m)}
        if m in others:
            variants["perturbation"] = bundle.with_tail(m, others[m])
        if entry.series and full is not None:
            for label, variant in variants.items():
                got = entry.series(variant)
                for key, values in full.items():
                    if not _same_arrays(values, got[key], keep):
                        found.append(f"{entry.name}.{key}: {label} at {m} changed past values")
        if entry.asof:
            t = m - 1
            base = canonical(entry.asof(bundle.head(m), t))
            for label, variant in {"full": bundle, **variants}.items():
                if label == "truncation":
                    continue  # that is `base` itself
                diff = _differs(base, canonical(entry.asof(variant, t)), entry.name)
                if diff:
                    found.append(f"{entry.name}: {label} at {m} changed as-of value ({diff})")
    return found
