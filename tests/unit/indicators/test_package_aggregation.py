# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Package aggregation and cross-checks (TS-IND-240, TS-IND-241)."""

from __future__ import annotations

import importlib
import inspect

import numpy as np

from supertrends import indicators
from supertrends.indicators import divergence, momentum
from tests.unit.indicators.lookahead_support import make_bundle

TOL = 1e-12
MODULE = "supertrends.indicators.supertrend"


def test_unit_indicators_function_may_share_its_module_name() -> None:
    """TS-IND-240: `supertrend` the function is exported next to the `supertrend` module."""
    module = importlib.import_module(MODULE)
    assert "supertrend" in module.__all__
    assert "supertrend" in indicators.__all__
    assert inspect.isfunction(indicators.supertrend)  # the function wins the package attribute
    assert len(indicators.__all__) == len(set(indicators.__all__))
    assert hasattr(module, "supertrend_weekly_direction")
    # the module stays reachable under a private alias after the star imports
    assert indicators._m_supertrend is module


def test_unit_divergence_private_macd_hist_equals_momentum_macd_hist() -> None:
    """TS-IND-241: divergence._macd_hist and momentum.macd(...).hist agree to 1e-12."""
    for seed in (1, 2, 3):
        close = make_bundle(seed, 500, intraday_from=None).close
        mine = divergence._macd_hist(close)
        theirs = momentum.macd(close).hist
        assert np.array_equal(np.isnan(mine), np.isnan(theirs))
        ok = ~np.isnan(mine)
        assert np.abs(mine[ok] - theirs[ok]).max() <= TOL
