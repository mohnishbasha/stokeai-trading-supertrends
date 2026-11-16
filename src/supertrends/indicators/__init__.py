# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Pure indicator math (ARCHITECTURE section 2, Signal Engine Specification).

Indicators take numpy float64 arrays and return arrays of the same length (NaN during warm-up)
or frozen dataclass records. They do no I/O, read no clock, use no randomness, hold no globals,
and import nothing from api, cli, mcp, data, or runs.

This module aggregates the public names of every indicator module, so
`supertrends.indicators.__all__` lists every public indicator function. The rule for tasks that
add indicators: add the function to your own module's `__all__`; never edit this file.
"""

from supertrends.indicators import (
    divergence,
    fibonacci,
    flow,
    levels,
    meanrev,
    momentum,
    primitives,
    supertrend,
    trend,
    volatility,
    volume,
)
from supertrends.indicators.divergence import *
from supertrends.indicators.fibonacci import *
from supertrends.indicators.flow import *
from supertrends.indicators.levels import *
from supertrends.indicators.meanrev import *
from supertrends.indicators.momentum import *
from supertrends.indicators.primitives import *
from supertrends.indicators.supertrend import *
from supertrends.indicators.trend import *
from supertrends.indicators.volatility import *
from supertrends.indicators.volume import *

__all__: list[str] = []
__all__ += divergence.__all__
__all__ += fibonacci.__all__
__all__ += flow.__all__
__all__ += levels.__all__
__all__ += meanrev.__all__
__all__ += momentum.__all__
__all__ += primitives.__all__
__all__ += supertrend.__all__
__all__ += trend.__all__
__all__ += volatility.__all__
__all__ += volume.__all__
