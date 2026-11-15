# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""TradingView parity for Supertrend (TS-IND-021, TS-IND-022; TEST_PLAN section 5).

Every CSV in tests/golden/tradingview/ is compared after the first 100 bars: the line within
0.01 and the direction exactly (TradingView's sign is converted at the import boundary by
`tests/golden/tradingview_support.py`). With no export present both tests skip visibly.
"""

from pathlib import Path

import numpy as np
import pytest

from supertrends.indicators.supertrend import supertrend
from tests.golden.tradingview_support import load_export

EXPORT_DIR = Path(__file__).parent / "tradingview"
WARMUP = 100
LINE_TOLERANCE = 0.01
SKIP_REASON = "TradingView export not yet provided (owner checklist item open)"

FILES = sorted(EXPORT_DIR.glob("*.csv"))
PARAMS = (
    [pytest.param(f, id=f.stem) for f in FILES]
    if FILES
    else [pytest.param(None, marks=pytest.mark.skip(reason=SKIP_REASON), id="no-export")]
)


@pytest.mark.parametrize("path", PARAMS)
def test_golden_supertrend_tradingview_parity_line_within_0_01_after_100_bar_warmup(
    path: Path,
) -> None:
    """TS-IND-021: line within 0.01 on every bar after the first 100."""
    export = load_export(path)
    assert len(export.close) > WARMUP, "export must hold more than 100 bars"
    res = supertrend(export.high, export.low, export.close, 10, 3.0)
    ours, theirs = res.line[WARMUP:], export.line[WARMUP:]
    assert not np.isnan(theirs).any(), "TradingView line missing after warm-up"
    assert not np.isnan(ours).any()
    worst = float(np.max(np.abs(ours - theirs)))
    assert worst <= LINE_TOLERANCE, f"max line difference {worst} in {path.name}"


@pytest.mark.parametrize("path", PARAMS)
def test_golden_supertrend_tradingview_parity_direction_matches_every_bar_after_warmup(
    path: Path,
) -> None:
    """TS-IND-022: direction identical on every bar after the first 100."""
    export = load_export(path)
    assert len(export.close) > WARMUP, "export must hold more than 100 bars"
    res = supertrend(export.high, export.low, export.close, 10, 3.0)
    mismatches = np.flatnonzero(res.direction[WARMUP:] != export.direction[WARMUP:])
    assert mismatches.size == 0, (
        f"direction differs at bars {(mismatches + WARMUP)[:10]} in {path.name}"
    )
