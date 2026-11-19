# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor framework (Signal Engine Specification, Conventions; ARCHITECTURE section 2; ADR-059).

A factor reads the indicator snapshot (`scoring.snapshot.compute_snapshot`) and a `FactorContext`
and returns a `FactorResult`: a score in the closed range -100 to +100, a list of evidence items
(name, value, unit, human reason; TS-SCR-004), a quality flag, and an optional weight multiplier.
The registry maps factor IDs to factors and iterates them in the order of `weights` in the scoring
config. Reasons come from `ReasonTemplate`s: deterministic strings with named placeholders whose
numbers are formatted by `format_number`, so the narrative guard can find every number in a reason
in the evidence document.

Everything here is pure: no I/O, clock, randomness, or module-level mutable state. Factors are
plain objects listed explicitly in `supertrends.scoring.factors`; nothing is registered by an
import side effect.
"""

from __future__ import annotations

import math
import string
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Protocol, Self, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from supertrends.scoring.config import ScoringConfig

__all__ = [
    "CONFIDENCE_INPUT_PATHS",
    "REGIME_INPUT_PATHS",
    "SCORE_MAX",
    "SCORE_MIN",
    "SELECTION_INPUT_PATHS",
    "EvidenceItem",
    "Factor",
    "FactorContext",
    "FactorRegistry",
    "FactorResult",
    "Quality",
    "ReasonTemplate",
    "expand_input_paths",
    "format_number",
    "get_path",
]

SCORE_MIN = -100.0
SCORE_MAX = 100.0
SMA_PERIOD_TOKEN = "<period>"  # noqa: S105 - a path placeholder, not a credential

# Snapshot paths read outside the factors (S3-T01 audit). `tests/unit/scoring` walks them against
# a computed snapshot, so the regime, confidence and selection tasks can rely on them.
REGIME_INPUT_PATHS: tuple[str, ...] = ("daily.adx.adx",)
CONFIDENCE_INPUT_PATHS: tuple[str, ...] = (
    "daily.atr_pct_rank",  # - 15 if atr_pct_rank > 90
    "daily.supertrend.direction",  # st_dir_d
    "weekly.supertrend_direction",  # - 10 if st_dir_w != st_dir_d
    "ripster.stack",  # - 10 if rc_stack == -st_dir_d
)
SELECTION_INPUT_PATHS: tuple[str, ...] = (
    "daily.supertrend.direction",  # st_dir_d
    "ripster.bias",  # rc_bias gate
    "daily.avg_dollar_volume_20d",  # liquidity floor
    "daily.relative_volume",  # ranking tie-breaker
    "daily.bars_since_flip",  # ranking tie-breaker
)


class Quality(StrEnum):
    """Factor quality flag (Conventions: ok, degraded, missing; ARCHITECTURE `factor_scores`).

    `daily_estimate` is Factor 10's quality when 5-minute bars are not available (weight x 0.6).
    """

    OK = "ok"
    DEGRADED = "degraded"
    MISSING = "missing"
    DAILY_ESTIMATE = "daily_estimate"


_Scalar = float | int | str | bool | None


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceItem(_Record):
    """One piece of evidence: a named value with its unit and the human reason (TS-SCR-004)."""

    name: Annotated[str, Field(min_length=1)]
    value: _Scalar
    unit: Annotated[str, Field(min_length=1)]
    reason: Annotated[str, Field(min_length=1)]

    @field_validator("value")
    @classmethod
    def _finite(cls, value: _Scalar) -> _Scalar:
        if isinstance(value, float) and not math.isfinite(value):
            msg = "evidence value must be finite (use None for not available)"
            raise ValueError(msg)
        return value


class FactorResult(_Record):
    """The output of one factor.

    `score` is in [-100, 100] and never NaN. A `missing` factor has score 0 and is left out of
    the composite and its weight redistributed (spec, Factor 11). `weight_multiplier` carries the
    quality discount on the factor's weight (0.6 for the Factor 10 daily estimate, 0.5 for stale
    fundamentals); the weights step applies it (ARCHITECTURE ADR-038).
    """

    factor_id: Annotated[str, Field(min_length=1)]
    score: Annotated[float, Field(ge=SCORE_MIN, le=SCORE_MAX, allow_inf_nan=False)]
    quality: Quality
    evidence: tuple[EvidenceItem, ...] = ()
    weight_multiplier: Annotated[float, Field(gt=0, allow_inf_nan=False)] = 1.0

    @model_validator(mode="after")
    def _missing_scores_zero(self) -> Self:
        if self.quality is Quality.MISSING and self.score != 0:
            msg = "a factor with quality missing must have score 0"
            raise ValueError(msg)
        return self

    @classmethod
    def missing(cls, factor_id: str, *, reason: str) -> Self:
        """A `missing` result: score 0, excluded from the composite, one explanatory item."""
        item = EvidenceItem(name="data_available", value=False, unit="flag", reason=reason)
        return cls(factor_id=factor_id, score=0.0, quality=Quality.MISSING, evidence=(item,))

    @property
    def is_missing(self) -> bool:
        return self.quality is Quality.MISSING

    @property
    def reasons(self) -> tuple[str, ...]:
        """The reason of every evidence item, in order."""
        return tuple(e.reason for e in self.evidence)


@dataclass(frozen=True)
class FactorContext:
    """Everything a factor may read besides the snapshot.

    `regime`, `fundamentals`, `days_to_earnings` and `event_risk` are injected by the caller;
    Sprint 3 leaves them unset (fundamentals and regimes arrive in Sprint 5), and the factors
    that read them are tested with injected values.
    """

    config: ScoringConfig
    as_of: date
    regime: str | None = None
    fundamentals: Mapping[str, Any] | None = None
    days_to_earnings: int | None = None
    event_risk: bool = False


@runtime_checkable
class Factor(Protocol):
    """A scoring factor. `id` is a key of `weights` in the scoring config.

    `input_paths` lists the snapshot paths the factor reads (dotted; `<period>` expands over
    `sma.periods`). `compute` is pure and deterministic.
    """

    id: str
    input_paths: tuple[str, ...]

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult: ...


class FactorRegistry:
    """Factors by ID. Build it from an explicit list; there is no global registry."""

    def __init__(self, factors: Iterable[Factor] = ()) -> None:
        self._factors: dict[str, Factor] = {}
        for factor in factors:
            self.register(factor)

    def register(self, factor: Factor) -> None:
        if not factor.id:
            msg = "a factor needs a non-empty id"
            raise ValueError(msg)
        if factor.id in self._factors:
            msg = f"factor {factor.id!r} is already registered"
            raise ValueError(msg)
        self._factors[factor.id] = factor

    def get(self, factor_id: str) -> Factor:
        try:
            return self._factors[factor_id]
        except KeyError:
            msg = f"no factor {factor_id!r}; registered: {sorted(self._factors)}"
            raise KeyError(msg) from None

    def ids(self) -> tuple[str, ...]:
        """Registered IDs in registration order."""
        return tuple(self._factors)

    def validate_against(self, config: ScoringConfig) -> None:
        """Raise ValueError unless the config weight IDs and the registered IDs are the same set."""
        weighted = set(config.weights.as_dict())
        registered = set(self._factors)
        problems = []
        if weighted - registered:
            problems.append(f"config weights without a factor: {sorted(weighted - registered)}")
        if registered - weighted:
            problems.append(f"factors without a config weight: {sorted(registered - weighted)}")
        if problems:
            raise ValueError("; ".join(problems))

    def ordered(self, config: ScoringConfig) -> tuple[Factor, ...]:
        """The factors in the order of `weights` in the config (validated first)."""
        self.validate_against(config)
        return tuple(self._factors[fid] for fid in config.weights.as_dict())

    def __iter__(self) -> Iterator[Factor]:
        return iter(self._factors.values())

    def __len__(self) -> int:
        return len(self._factors)

    def __contains__(self, factor_id: object) -> bool:
        return factor_id in self._factors


def format_number(value: float | int | str | bool) -> str:
    """The one number format for reasons: ints as is, floats fixed to 2 decimals.

    Booleans are `true` or `false`; strings pass through. Non-finite floats raise ValueError, so
    NaN never appears in a reason. Negative zero prints as `0.00`.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            msg = f"cannot format a non-finite number: {value!r}"
            raise ValueError(msg)
        text = f"{value:.2f}"
        return "0.00" if text == "-0.00" else text
    return value


@dataclass(frozen=True)
class ReasonTemplate:
    """A deterministic reason string with named placeholders, e.g. `"... flipped {direction}"`.

    Placeholders are bare names (no positional, attribute, index, conversion or format spec);
    values are formatted by `format_number`. Rendering needs exactly the placeholders' values.
    Doubled braces are literal braces.
    """

    id: str
    template: str

    def __post_init__(self) -> None:
        if not self.id:
            msg = "a reason template needs a non-empty id"
            raise ValueError(msg)
        for _, field, spec, conv in string.Formatter().parse(self.template):
            if field is None:
                continue
            if not field.isidentifier() or spec or conv:
                msg = f"template {self.id!r} must use only named placeholders, got {{{field}}}"
                raise ValueError(msg)

    @property
    def placeholders(self) -> tuple[str, ...]:
        names: list[str] = []
        for _, field, _, _ in string.Formatter().parse(self.template):
            if field is not None and field not in names:
                names.append(field)
        return tuple(names)

    def render(self, **values: float | int | str | bool) -> str:
        expected = self.placeholders
        for name in expected:
            if name not in values:
                raise KeyError(name)
        for name in values:
            if name not in expected:
                raise KeyError(name)
        out = []
        for literal, field, _, _ in string.Formatter().parse(self.template):
            out.append(literal)
            if field is not None:
                out.append(format_number(values[field]))
        return "".join(out)

    def evidence(
        self, name: str, value: _Scalar, unit: str, /, **placeholders: float | int | str | bool
    ) -> EvidenceItem:
        """An evidence item whose reason is this template rendered with `placeholders`."""
        return EvidenceItem(name=name, value=value, unit=unit, reason=self.render(**placeholders))


def get_path(snapshot: Mapping[str, Any], path: str) -> Any:
    """The value at a dotted snapshot path. KeyError names the path if a segment is missing.

    A present key whose value is null returns None; going through a null raises KeyError.
    """
    node: Any = snapshot
    for segment in path.split("."):
        if not isinstance(node, Mapping) or segment not in node:
            msg = f"snapshot path {path!r} is missing at {segment!r}"
            raise KeyError(msg)
        node = node[segment]
    return node


def expand_input_paths(paths: Iterable[str], config: ScoringConfig) -> tuple[str, ...]:
    """Expand `<period>` over `config.sma.periods`; other paths pass through."""
    out: list[str] = []
    for path in paths:
        if SMA_PERIOD_TOKEN in path:
            out.extend(path.replace(SMA_PERIOD_TOKEN, str(p)) for p in config.sma.periods)
        else:
            out.append(path)
    return tuple(out)
