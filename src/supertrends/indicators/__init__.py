# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Pure indicator math (ARCHITECTURE section 2, Signal Engine Specification).

Indicators take numpy float64 arrays and return arrays of the same length (NaN during warm-up)
or frozen dataclass records. They do no I/O, read no clock, use no randomness, hold no globals,
and import nothing from api, cli, mcp, data, or runs.

This module aggregates the public names of every indicator module, so
`supertrends.indicators.__all__` lists every public indicator function. The rule for tasks that
add indicators: add the function to your own module's `__all__`; never edit this file.

A function may share its module's name (`supertrend.supertrend`): each module is imported under a
private alias (`_m_<name>`) before the star imports, and `__all__` is built from the aliases, so
the star import that rebinds `supertrends.indicators.supertrend` to the function cannot break the
aggregation. Consequence: `from supertrends.indicators import supertrend` is the function; reach
the module with `from supertrends.indicators.supertrend import ...` or `importlib.import_module`.
"""

from supertrends.indicators import divergence as _m_divergence
from supertrends.indicators import fibonacci as _m_fibonacci
from supertrends.indicators import flow as _m_flow
from supertrends.indicators import levels as _m_levels
from supertrends.indicators import meanrev as _m_meanrev
from supertrends.indicators import momentum as _m_momentum
from supertrends.indicators import primitives as _m_primitives
from supertrends.indicators import supertrend as _m_supertrend
from supertrends.indicators import trend as _m_trend
from supertrends.indicators import volatility as _m_volatility
from supertrends.indicators import volume as _m_volume
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
__all__ += _m_divergence.__all__
__all__ += _m_fibonacci.__all__
__all__ += _m_flow.__all__
__all__ += _m_levels.__all__
__all__ += _m_meanrev.__all__
__all__ += _m_momentum.__all__
__all__ += _m_primitives.__all__
__all__ += _m_supertrend.__all__
__all__ += _m_trend.__all__
__all__ += _m_volatility.__all__
__all__ += _m_volume.__all__
