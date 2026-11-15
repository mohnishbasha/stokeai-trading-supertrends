# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Registry of every public indicator for the no-look-ahead and determinism harness (STUB)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class Bundle:
    """OHLCV daily bars plus optional 5-minute bars (STUB)."""

    dates: NDArray[np.datetime64]
    open: FloatArray
    high: FloatArray
    low: FloatArray
    close: FloatArray
    volume: FloatArray
    i_day: NDArray[np.int64]
    bar_start: NDArray[np.datetime64]
    i_high: FloatArray
    i_low: FloatArray
    i_close: FloatArray
    i_volume: FloatArray

    def __len__(self) -> int:
        return len(self.close)

    def head(self, m: int) -> Bundle:
        raise NotImplementedError

    def with_tail(self, m: int, other: Bundle) -> Bundle:
        raise NotImplementedError


@dataclass(frozen=True)
class Entry:
    """One registered indicator (STUB)."""

    name: str
    series: Callable[[Bundle], dict[str, FloatArray]] | None = None
    asof: Callable[[Bundle, int], object] | None = None
    confirm_lag: int = 0


REGISTRY: dict[str, Entry] = {}
EXEMPT: dict[str, str] = {}


def unregistered(
    names: list[str] | None = None, registry: dict[str, Entry] | None = None
) -> list[str]:
    raise NotImplementedError


def canonical(obj: Any) -> object:
    raise NotImplementedError


def compute_all(bundle: Bundle, registry: dict[str, Entry] | None = None) -> dict[str, object]:
    raise NotImplementedError
