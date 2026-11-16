# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""TradingView parity for Ripster EMA Clouds (TS-IND-141, TS-IND-142; FR-224, ADR-058).

Every CSV in tests/golden/tradingview/ that carries the Ripster EMA Clouds plots is computed on
its own bars and compared after the first 200 bars: each of the ten EMAs within 0.01, and each
cloud direction exactly (TradingView colors a cloud by its short EMA against its long EMA). With
no such export present both tests skip visibly.
"""

from pathlib import Path

import numpy as np
import pytest

from supertrends.indicators.ripster_clouds import RIPSTER_CLOUDS, ripster_clouds
from tests.golden.tradingview_support import RipsterExport, load_ripster_export

EXPORT_DIR = Path(__file__).parent / "tradingview"
WARMUP = 200
EMA_TOLERANCE = 0.01
SKIP_REASON = "TradingView Ripster EMA Clouds export not yet provided (owner checklist item open)"

EXPORTS = [(f, load_ripster_export(f)) for f in sorted(EXPORT_DIR.glob("*.csv"))]
FOUND = [(f, e) for f, e in EXPORTS if e is not None]
PARAMS = (
    [pytest.param(e, id=f.stem) for f, e in FOUND]
    if FOUND
    else [pytest.param(None, marks=pytest.mark.skip(reason=SKIP_REASON), id="no-export")]
)


def _ours(export: RipsterExport) -> dict[int, np.ndarray]:
    assert len(export.close) > WARMUP, "export must hold more than 200 bars"
    res = ripster_clouds(export.high, export.low, export.close)
    out: dict[int, np.ndarray] = {}
    for cloud, (short, long) in zip(res.clouds, RIPSTER_CLOUDS, strict=True):
        out[short], out[long] = cloud.ema_short, cloud.ema_long
    return out


@pytest.mark.parametrize("export", PARAMS)
def test_golden_ripster_clouds_tradingview_parity_each_ema_within_0_01_after_200_bar_warmup(
    export: RipsterExport,
) -> None:
    """TS-IND-141: all ten EMAs within 0.01 on every bar after the first 200."""
    ours = _ours(export)
    for period, theirs in export.emas.items():
        mine, tv = ours[period][WARMUP:], theirs[WARMUP:]
        assert not np.isnan(tv).any(), f"TradingView EMA {period} missing after warm-up"
        worst = float(np.max(np.abs(mine - tv)))
        assert worst <= EMA_TOLERANCE, f"EMA {period}: max difference {worst}"


@pytest.mark.parametrize("export", PARAMS)
def test_golden_ripster_clouds_tradingview_parity_cloud_direction_matches_every_bar_after_warmup(
    export: RipsterExport,
) -> None:
    """TS-IND-142: every cloud direction identical on every bar after the first 200."""
    res = ripster_clouds(export.high, export.low, export.close)
    for i, (cloud, (short, long)) in enumerate(zip(res.clouds, RIPSTER_CLOUDS, strict=True)):
        tv = np.where(export.emas[short] > export.emas[long], 1.0, -1.0)[WARMUP:]
        bad = np.flatnonzero(cloud.direction[WARMUP:] != tv)
        assert bad.size == 0, f"c{i + 1} direction differs at bars {(bad + WARMUP)[:10]}"
