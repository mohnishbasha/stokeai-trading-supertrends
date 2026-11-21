# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Shared builders for the selection tests (S3-T06)."""

from __future__ import annotations

import dataclasses
import random
from collections.abc import Sequence
from datetime import date, timedelta
from functools import cache
from typing import Any

from supertrends.scoring.composite import ScoreCard, score_ticker
from supertrends.scoring.config import ScoringConfig
from supertrends.selection.candidates import SelectionInput
from tests.unit.scoring.cmp_support import load_cfg, make_context, make_results, make_snapshot

START = date(2026, 1, 1)


@cache
def cfg() -> ScoringConfig:
    return load_cfg()


def with_selection(config: ScoringConfig, **over: Any) -> ScoringConfig:
    """A copy of `config` with `selection.*` keys replaced."""
    return config.model_copy(update={"selection": config.selection.model_copy(update=over)})


def with_gate(config: ScoringConfig, *, enabled: bool) -> ScoringConfig:
    ripster = config.ripster.model_copy(update={"selection_bias_gate": enabled})
    return config.model_copy(update={"ripster": ripster})


@cache
def _base_card() -> ScoreCard:
    c = cfg()
    return score_ticker(make_snapshot(), make_results(default=50.0), make_context(c))


def card(display: float, confidence: float) -> ScoreCard:
    """A real score card with the display score and confidence replaced."""
    return dataclasses.replace(_base_card(), display_score=display, confidence=confidence)


def buy(
    ticker: str,
    display: float = 70.0,
    *,
    confidence: float = 60.0,
    st_dir_d: int | None = 1,
    rc_bias: int | None = 1,
    bars_since_flip: int | None = 3,
    relative_volume: float | None = 1.0,
    adv: float | None = 25_000_000.0,
    quality: str = "ok",
    buy_shift: float = 0.0,
    sell_shift: float = 0.0,
) -> SelectionInput:
    """An input that qualifies as a buy under the seed config unless a field says otherwise."""
    return SelectionInput(
        ticker=ticker,
        card=card(display, confidence),
        st_dir_d=st_dir_d,
        rc_bias=rc_bias,
        bars_since_flip=bars_since_flip,
        relative_volume=relative_volume,
        avg_dollar_volume_20d=adv,
        data_quality=quality,
        buy_threshold_shift=buy_shift,
        sell_threshold_shift=sell_shift,
    )


def sell(
    ticker: str,
    display: float = 30.0,
    *,
    st_dir_d: int | None = -1,
    rc_bias: int | None = -1,
    **over: Any,
) -> SelectionInput:
    """An input that qualifies as a sell under the seed config unless a field says otherwise."""
    return buy(ticker, display, st_dir_d=st_dir_d, rc_bias=rc_bias, **over)


def closes_from_returns(returns: Sequence[float], start: float = 100.0) -> dict[date, float]:
    """Dated closes (consecutive calendar days from START) compounding `returns`."""
    out = {START: start}
    price = start
    for i, r in enumerate(returns, start=1):
        price *= 1.0 + r
        out[START + timedelta(days=i)] = price
    return out


def random_returns(seed: int, n: int = 80, scale: float = 0.01) -> list[float]:
    """Seeded Gaussian returns; independent seeds are far from 0.9 correlated over 60 bars."""
    rng = random.Random(seed)  # noqa: S311 - deterministic test data, not security
    return [rng.gauss(0.0, scale) for _ in range(n)]


def independent_closes(tickers: Sequence[str]) -> dict[str, dict[date, float]]:
    return {t: closes_from_returns(random_returns(1000 + i)) for i, t in enumerate(tickers)}


def near_duplicate_closes(seed: int, names: Sequence[str]) -> dict[str, dict[date, float]]:
    """Closes for tickers that track one return series with tiny noise (SPY, VOO, IVV)."""
    base = random_returns(seed)
    out: dict[str, dict[date, float]] = {}
    for i, name in enumerate(names):
        noise = random_returns(seed + 100 + i, scale=0.0005)
        out[name] = closes_from_returns([b + e for b, e in zip(base, noise, strict=True)])
    return out
