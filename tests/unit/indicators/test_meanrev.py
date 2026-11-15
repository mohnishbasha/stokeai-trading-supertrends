# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Mean-reversion indicator tests (TS-IND-081, TS-IND-082, TS-IND-210 to TS-IND-212).

Expected values come from plain-Python loops written here, never from the code under test.
"""

import math

import numpy as np
from numpy.typing import NDArray

from supertrends import indicators
from supertrends.indicators import meanrev

TOL = 1e-6


def closes(count: int = 40) -> NDArray[np.float64]:
    return np.array(
        [100.0 + 5.0 * math.sin(i / 3.0) + 0.1 * i + (i % 7) * 0.3 for i in range(count)],
        dtype=np.float64,
    )


def ref_window(values: list[float], t: int, n: int = 20) -> tuple[float, float]:
    """Independent SMA and population stdev of the n values ending at t."""
    w = values[t - n + 1 : t + 1]
    mean = sum(w) / n
    var = sum((v - mean) ** 2 for v in w) / n
    return mean, math.sqrt(var)


def test_bollinger_golden_1_to_20() -> None:
    """TS-IND-081: closes 1..20 give hand-derived bands, %B, and bandwidth at the last bar.

    SMA = 10.5; population variance = (20^2 - 1) / 12 = 33.25, stdev = 5.766281297335398.
    upper = 10.5 + 2*sd = 22.0325625946708, lower = 10.5 - 2*sd = -1.0325625946708.
    %B = (20 - lower) / (4*sd) = 21.0325625946708 / 23.0651251893416 = 0.91188.
    """
    close = np.arange(1.0, 21.0)
    sd = math.sqrt(33.25)
    bands = meanrev.bollinger(close)
    assert abs(bands.middle[-1] - 10.5) < TOL
    assert abs(bands.upper[-1] - (10.5 + 2 * sd)) < TOL
    assert abs(bands.lower[-1] - (10.5 - 2 * sd)) < TOL
    assert abs(float(bands.upper[-1]) - 22.0325625946708) < TOL
    assert abs(meanrev.pct_b(close)[-1] - (20 - (10.5 - 2 * sd)) / (4 * sd)) < TOL
    assert abs(meanrev.pct_b(close)[-1] - 0.91188) < 1e-4
    assert np.isnan(bands.middle[:19]).all()
    assert np.isnan(meanrev.pct_b(close)[:19]).all()


def test_bollinger_golden_matches_reference_loop() -> None:
    """TS-IND-081: bands and %B match an independent loop within 1e-6 on a longer series."""
    close = closes()
    vals = close.tolist()
    bands = meanrev.bollinger(close, 20, 2.0)
    pb = meanrev.pct_b(close)
    for t in range(19, len(vals)):
        mean, sd = ref_window(vals, t)
        assert abs(bands.middle[t] - mean) < TOL
        assert abs(bands.upper[t] - (mean + 2 * sd)) < TOL
        assert abs(bands.lower[t] - (mean - 2 * sd)) < TOL
        assert abs(pb[t] - (vals[t] - (mean - 2 * sd)) / (4 * sd)) < TOL


def test_zscore_uses_population_stdev20_and_sma20() -> None:
    """TS-IND-082: z = (close - SMA20) / population stdev20.

    Closes 1..20: z = (20 - 10.5) / sqrt(33.25) = 1.647..., which differs from the sample
    stdev result 9.5 / sqrt(35) = 1.6058, so the population choice is pinned.
    """
    close = np.arange(1.0, 21.0)
    z = meanrev.zscore(close)
    assert abs(z[-1] - 9.5 / math.sqrt(33.25)) < TOL
    assert abs(z[-1] - 9.5 / math.sqrt(35.0)) > 1e-2
    vals = closes().tolist()
    zs = meanrev.zscore(closes())
    for t in range(19, len(vals)):
        mean, sd = ref_window(vals, t)
        assert abs(zs[t] - (vals[t] - mean) / sd) < TOL
    assert np.isnan(zs[:19]).all()


def test_flat_series_zero_width_is_nan() -> None:
    """TS-IND-210: a flat window (zero stdev) gives NaN %B and z-score, not inf or an error."""
    close = np.full(25, 50.0)
    assert np.isnan(meanrev.pct_b(close)).all()
    assert np.isnan(meanrev.zscore(close)).all()
    bands = meanrev.bollinger(close)
    assert bands.upper[-1] == bands.lower[-1] == 50.0


def test_short_input_all_nan_and_same_length() -> None:
    """TS-IND-211: input shorter than the window returns all NaN of the same length."""
    close = closes(10)
    bands = meanrev.bollinger(close)
    for arr in (
        bands.middle,
        bands.upper,
        bands.lower,
        meanrev.pct_b(close),
        meanrev.zscore(close),
    ):
        assert len(arr) == 10
        assert np.isnan(arr).all()


def test_exports_aggregated() -> None:
    """TS-IND-212: meanrev public names are in the module __all__ and the package aggregate."""
    for name in ("Bollinger", "bollinger", "pct_b", "zscore"):
        assert name in meanrev.__all__
        assert name in indicators.__all__
