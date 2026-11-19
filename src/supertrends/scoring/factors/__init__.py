# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""The twelve scoring factors, one module each (ARCHITECTURE section 2 and 13.2; ADR-059).

Every module exposes `FACTOR`, `FACTOR_ID` and `INPUT_PATHS`. `ALL_FACTORS` lists them in the order
of `weights` in `config/scoring.yaml`; the registry is built from this explicit list, not from
import side effects. The owning task of each module is in `OWNER_TASKS`.
"""

from supertrends.scoring.factor import Factor, FactorRegistry
from supertrends.scoring.factors import (
    divergence,
    fibonacci,
    flow,
    fundamentals,
    levels,
    macd,
    mean_reversion,
    ripster,
    sma,
    supertrend,
    volatility,
    volume_osc,
)

__all__ = ["ALL_FACTORS", "OWNER_TASKS", "default_registry"]

ALL_FACTORS: tuple[Factor, ...] = (
    supertrend.FACTOR,
    sma.FACTOR,
    macd.FACTOR,
    divergence.FACTOR,
    mean_reversion.FACTOR,
    fibonacci.FACTOR,
    levels.FACTOR,
    volatility.FACTOR,
    volume_osc.FACTOR,
    flow.FACTOR,
    fundamentals.FACTOR,
    ripster.FACTOR,
)

OWNER_TASKS: dict[str, str] = {
    "supertrend": "S3-T02",
    "sma": "S3-T02",
    "macd": "S3-T02",
    "divergence": "S3-T02",
    "mean_reversion": "S3-T03",
    "fibonacci": "S3-T03",
    "levels": "S3-T03",
    "volatility": "S3-T03",
    "volume_osc": "S3-T04",
    "flow": "S3-T04",
    "fundamentals": "S5-T04",
    "ripster": "S3-T14",
}


def default_registry() -> FactorRegistry:
    """A new registry holding all twelve factors."""
    return FactorRegistry(ALL_FACTORS)
