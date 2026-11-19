# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Scoring config model, loader, JSON schema, and config_hash (ARCHITECTURE section 13).

Every key in config/scoring.yaml is required and unknown keys are rejected at every level.
The one documented default is an omitted regime multiplier, which is 1.00 (ADR-037).
"""

import hashlib
import json
import math
from itertools import pairwise
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from supertrends.errors import ConfigError

FACTOR_IDS: tuple[str, ...] = (
    "supertrend",
    "sma",
    "macd",
    "divergence",
    "mean_reversion",
    "fibonacci",
    "levels",
    "volatility",
    "volume_osc",
    "flow",
    "fundamentals",
    "ripster",
)
REGIMES: tuple[str, ...] = ("trending", "ranging", "transitional")
REQUIRED_BENCHMARKS: frozenset[str] = frozenset({"SPY", "QQQ"})
WEIGHT_SUM = 100.0
WEIGHT_SUM_TOLERANCE = 1e-9
MAX_PICKS_PER_SIDE = 10
DEFAULT_REGIME_MULTIPLIER = 1.0

PosInt = Annotated[int, Field(gt=0)]
PosFloat = Annotated[float, Field(gt=0)]
NonNegFloat = Annotated[float, Field(ge=0)]
Percent = Annotated[float, Field(ge=0, le=100)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ScoringMeta(_Strict):
    version: Annotated[int, Field(ge=1)]


class Liquidity(_Strict):
    min_avg_dollar_volume_20d: PosFloat


class Supertrend(_Strict):
    atr_length: PosInt
    factor: PosFloat
    fresh_flip_bars: PosInt
    stretch_atr: PosFloat


class Sma(_Strict):
    periods: Annotated[list[PosInt], Field(min_length=1)]
    slope_bars: PosInt
    cross_lookback: PosInt


class Macd(_Strict):
    fast: PosInt
    slow: PosInt
    signal: PosInt
    cross_lookback: PosInt
    weekly_disagree_multiplier: PosFloat


class DivergencePoints(_Strict):
    rsi: NonNegFloat
    macd_hist: NonNegFloat
    obv: NonNegFloat


class Divergence(_Strict):
    pivot_width_daily: PosInt
    pivot_width_weekly: PosInt
    window_bars: PosInt
    recency_bars: PosInt
    points: DivergencePoints
    hidden_multiplier: PosFloat
    weekly_confirm_multiplier: PosFloat


class MeanReversion(_Strict):
    window: PosInt
    z_cap: PosFloat
    rsi_length: PosInt
    rsi_low: Percent
    rsi_high: Percent


class Fibonacci(_Strict):
    lookback_bars: PosInt
    min_reversal_pct: PosFloat
    min_reversal_atr: PosFloat
    near_atr: PosFloat


class Levels(_Strict):
    lookback_bars: PosInt
    pivot_width: PosInt
    cluster_atr: PosFloat
    breakout_rel_volume: PosFloat


class Volatility(_Strict):
    atr_length: PosInt
    bb_length: PosInt
    bb_mult: PosFloat
    squeeze_rank: Percent
    expansion_rank: Percent
    extreme_atr_rank: Percent


class Volume(_Strict):
    osc_short: PosInt
    osc_long: PosInt
    obv_slope_bars: PosInt


class Flow(_Strict):
    intraday_timeframe: Annotated[str, Field(pattern=r"^[1-9][0-9]*m$")]
    window_sessions: PosInt
    min_sessions_for_intraday: PosInt
    cmf_length: PosInt
    daily_estimate_weight_multiplier: PosFloat


class Fundamentals(_Strict):
    stale_days: PosInt
    stale_weight_multiplier: PosFloat


class RipsterCloudPairs(_Strict):
    """The five EMA clouds as (short, long) pairs (Factor 12)."""

    c1: tuple[PosInt, PosInt]
    c2: tuple[PosInt, PosInt]
    c3: tuple[PosInt, PosInt]
    c4: tuple[PosInt, PosInt]
    c5: tuple[PosInt, PosInt]

    @model_validator(mode="after")
    def _short_below_long(self) -> "RipsterCloudPairs":
        for name in ("c1", "c2", "c3", "c4", "c5"):
            short, long = getattr(self, name)
            if short >= long:
                msg = f"ripster.clouds.{name} must be [short, long] with short < long"
                raise ValueError(msg)
        return self

    def pairs(self) -> tuple[tuple[int, int], ...]:
        """The clouds c1 to c5 as (short, long) pairs, the shape `ripster_clouds` takes."""
        return (self.c1, self.c2, self.c3, self.c4, self.c5)


class RipsterPoints(_Strict):
    bias: NonNegFloat
    trend: NonNegFloat
    stack: NonNegFloat
    mid: NonNegFloat
    long: NonNegFloat
    pullback: NonNegFloat


class Ripster(_Strict):
    source: Literal["hl2"]
    ma_type: Literal["ema"]
    clouds: RipsterCloudPairs
    points: RipsterPoints
    pullback_lookback_bars: PosInt
    confidence_stack_conflict_penalty: NonNegFloat
    selection_bias_gate: bool


class Weights(_Strict):
    supertrend: NonNegFloat
    sma: NonNegFloat
    macd: NonNegFloat
    divergence: NonNegFloat
    mean_reversion: NonNegFloat
    fibonacci: NonNegFloat
    levels: NonNegFloat
    volatility: NonNegFloat
    volume_osc: NonNegFloat
    flow: NonNegFloat
    fundamentals: NonNegFloat
    ripster: NonNegFloat

    @model_validator(mode="after")
    def _sum_to_100(self) -> "Weights":
        total = sum(self.as_dict().values())
        if not math.isclose(total, WEIGHT_SUM, rel_tol=0, abs_tol=WEIGHT_SUM_TOLERANCE):
            msg = f"weights must sum to {WEIGHT_SUM:g}, got {total:g}"
            raise ValueError(msg)
        return self

    def as_dict(self) -> dict[str, float]:
        """Weights keyed by factor ID, in FACTOR_IDS order."""
        return {fid: float(getattr(self, fid)) for fid in FACTOR_IDS}


class Regime(_Strict):
    adx_length: PosInt
    trending_min: Percent
    ranging_max: Percent
    multipliers: dict[str, dict[str, PosFloat]]

    @field_validator("multipliers")
    @classmethod
    def _complete_multipliers(
        cls, value: dict[str, dict[str, float]]
    ) -> dict[str, dict[str, float]]:
        if set(value) != set(REGIMES):
            msg = f"regime.multipliers must have exactly {list(REGIMES)}, got {sorted(value)}"
            raise ValueError(msg)
        completed: dict[str, dict[str, float]] = {}
        for regime in REGIMES:
            cells = value[regime]
            unknown = sorted(set(cells) - set(FACTOR_IDS))
            if unknown:
                msg = f"regime.multipliers.{regime} has unknown factor ids {unknown}"
                raise ValueError(msg)
            completed[regime] = {
                fid: float(cells.get(fid, DEFAULT_REGIME_MULTIPLIER)) for fid in FACTOR_IDS
            }
        return completed

    @model_validator(mode="after")
    def _ordered(self) -> "Regime":
        if self.ranging_max > self.trending_min:
            msg = "regime.ranging_max must be <= regime.trending_min"
            raise ValueError(msg)
        return self


class Events(_Strict):
    earnings_window_days: PosInt
    earnings_fundamentals_multiplier: PosFloat


class Thresholds(_Strict):
    buy_display_min: Percent
    sell_display_max: Percent
    min_confidence: Percent
    weak_fundamentals_score: float
    strong_fundamentals_score: float
    fundamentals_threshold_shift: NonNegFloat
    market_regime_threshold_shift: NonNegFloat

    @model_validator(mode="after")
    def _ordered(self) -> "Thresholds":
        if self.sell_display_max >= self.buy_display_min:
            msg = "thresholds.sell_display_max must be < thresholds.buy_display_min"
            raise ValueError(msg)
        return self


class Selection(_Strict):
    max_buys: Annotated[int, Field(ge=0, le=MAX_PICKS_PER_SIDE)]
    max_sells: Annotated[int, Field(ge=0, le=MAX_PICKS_PER_SIDE)]
    correlation_window: PosInt
    correlation_max: Annotated[float, Field(gt=0, le=1)]


class TrackRecord(_Strict):
    horizons_days: Annotated[list[PosInt], Field(min_length=1)]
    small_sample: PosInt

    @field_validator("horizons_days")
    @classmethod
    def _ascending(cls, value: list[int]) -> list[int]:
        if any(b <= a for a, b in pairwise(value)):
            msg = "track_record.horizons_days must be strictly ascending"
            raise ValueError(msg)
        return value


class ScoringConfig(_Strict):
    """The validated scoring config document."""

    scoring: ScoringMeta
    min_history_bars: PosInt
    liquidity: Liquidity
    supertrend: Supertrend
    sma: Sma
    macd: Macd
    divergence: Divergence
    mean_reversion: MeanReversion
    fibonacci: Fibonacci
    levels: Levels
    volatility: Volatility
    volume: Volume
    flow: Flow
    fundamentals: Fundamentals
    ripster: Ripster
    weights: Weights
    regime: Regime
    events: Events
    thresholds: Thresholds
    selection: Selection
    benchmarks: Annotated[list[str], Field(min_length=1)]
    track_record: TrackRecord

    @field_validator("benchmarks")
    @classmethod
    def _required_benchmarks(cls, value: list[str]) -> list[str]:
        missing = sorted(REQUIRED_BENCHMARKS - set(value))
        if missing:
            msg = f"benchmarks must include {missing}"
            raise ValueError(msg)
        return value


def parse_scoring_config(data: object) -> ScoringConfig:
    """Validate a parsed YAML document. Raises ConfigError naming every bad key."""
    if not isinstance(data, dict):
        msg = "scoring config must be a mapping at the top level"
        raise ConfigError(msg)
    try:
        return ScoringConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(_describe(exc)) from exc


def load_scoring_config(path: str | Path) -> ScoringConfig:
    """Read and validate a scoring config file."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        msg = f"scoring config not found: {p}"
        raise ConfigError(msg) from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        msg = f"scoring config is not valid YAML: {p}: {exc}"
        raise ConfigError(msg) from exc
    return parse_scoring_config(data)


def canonical_json(cfg: ScoringConfig) -> str:
    """Canonical JSON of the validated document (sorted keys, no whitespace)."""
    return json.dumps(
        cfg.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def config_hash(cfg: ScoringConfig) -> str:
    """Return "sha256:<hex>" of the canonical JSON. Includes scoring.version (ADR-026)."""
    return "sha256:" + hashlib.sha256(canonical_json(cfg).encode("utf-8")).hexdigest()


def json_schema() -> dict[str, Any]:
    """JSON schema of the scoring config, as committed in docs/schemas/scoring.schema.json."""
    return ScoringConfig.model_json_schema()


def _describe(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        key = ".".join(str(p) for p in err["loc"]) or "scoring config"
        parts.append(f"{key}: {err['msg']}")
    return "; ".join(parts)
