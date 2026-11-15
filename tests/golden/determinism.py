# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Canonical hashes of the synthetic dataset and of every indicator output on it.

TEST_PLAN sections 5.5 and 7.1. The dataset is the fixture provider's universe (all tickers,
fixed seed, fixed as-of date = the last fixture session). Serialization is canonical JSON:
sorted keys, compact separators, floats via `repr` of the IEEE 754 double, NaN as null, ASCII.
Run `python -m tests.golden.determinism` to print both hashes (used by scripts/regen-golden.sh).
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from supertrends.data.providers.fixture import FixtureProvider, FixtureUniverse
from supertrends.indicators.registry import Bundle, compute_all

GOLDEN_DIR = Path(__file__).parent
SEED = 20261114
AS_OF = date(2026, 11, 13)  # the last fixture session
START = date(2023, 1, 1)
_NY = ZoneInfo("America/New_York")


def _dump(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def provider() -> FixtureProvider:
    return FixtureProvider(FixtureUniverse(seed=SEED, end_date=AS_OF))


def symbols() -> list[str]:
    return sorted(FixtureUniverse.symbols())


def bundle_for(fixture: FixtureProvider, symbol: str) -> Bundle:
    """Daily bars and 5-minute bars of one symbol as arrays (session-local wall-clock starts)."""
    daily = fixture.daily_bars(symbol, START, AS_OF)
    intraday = fixture.intraday_bars(symbol, START, AS_OF)
    dates = np.array([b.ts.date() for b in daily], dtype="datetime64[D]")
    day_of = {d: i for i, d in enumerate(dates.tolist())}
    starts = [b.ts.astimezone(_NY).replace(tzinfo=None) for b in intraday]
    return Bundle(
        dates=dates,
        open=np.array([b.open for b in daily]),
        high=np.array([b.high for b in daily]),
        low=np.array([b.low for b in daily]),
        close=np.array([b.close for b in daily]),
        volume=np.array([float(b.volume) for b in daily]),
        i_day=np.array([day_of[s.date()] for s in starts], dtype=np.int64),
        bar_start=np.array(starts, dtype="datetime64[m]"),
        i_high=np.array([b.high for b in intraday]),
        i_low=np.array([b.low for b in intraday]),
        i_close=np.array([b.close for b in intraday]),
        i_volume=np.array([float(b.volume) for b in intraday]),
    )


def synthetic_dataset_hash() -> str:
    """sha256 of the canonical serialization of every generated bar (TS-ING-003)."""
    fixture = provider()
    digest = hashlib.sha256()
    for symbol in symbols():
        rows = {
            "symbol": symbol,
            "daily": [
                [b.ts.isoformat(), b.open, b.high, b.low, b.close, b.volume]
                for b in fixture.daily_bars(symbol, START, AS_OF)
            ],
            "intraday": [
                [b.ts.isoformat(), b.open, b.high, b.low, b.close, b.volume]
                for b in fixture.intraday_bars(symbol, START, AS_OF)
            ],
        }
        digest.update(_dump(rows))
    return digest.hexdigest()


def determinism_hash() -> str:
    """sha256 of every registered indicator output for every ticker (TS-IND-093)."""
    fixture = provider()
    digest = hashlib.sha256()
    for symbol in symbols():
        outputs = compute_all(bundle_for(fixture, symbol))
        digest.update(_dump({"symbol": symbol, "outputs": outputs}))
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    """Print `synthetic_dataset <hash>` and `determinism <hash>`; `--write` updates the files."""
    hashes = {"synthetic_dataset": synthetic_dataset_hash(), "determinism": determinism_hash()}
    for name, value in hashes.items():
        print(f"{name} {value}")  # noqa: T201
        if "--write" in argv:
            (GOLDEN_DIR / f"{name}.sha256").write_text(value + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
