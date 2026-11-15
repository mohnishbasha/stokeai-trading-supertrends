# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Derivation of the TS-IND-020 hand-computed Supertrend fixture.

Plain-Python reference written straight from BUILD_PROMPT Factor 1 (it never imports
`supertrends`). Run `python tests/golden/handcomputed/supertrend_40bar_derive.py --write` to
rebuild `supertrend_40bar.json`. Per golden policy 5.5 item 6 the fixture is never regenerated
from the implementation; this script is the independent derivation, and a few rows are checked
by hand in tests/unit/indicators/test_supertrend.py.

Design: atr_length = 3, factor = 1.5. High = close + 1 and low = close - 1, so TR is 2 on calm
bars and larger on gaps. Bars 0-9 drift down, 10-19 rally (up flip), 20-29 grind up (the lower
band ratchets up), 30-39 crash (down flip) and then the upper band ratchets down.
"""

import json
import sys
from pathlib import Path

ATR_LENGTH = 3
FACTOR = 1.5
CLOSES = [
    100, 99, 98, 97, 96, 95, 96, 95, 94, 93,
    95, 98, 101, 104, 106, 108, 109, 111, 112, 114,
    113, 114, 115, 116, 115, 117, 118, 119, 120, 121,
    117, 112, 108, 105, 103, 104, 102, 100, 99, 98,
]  # fmt: skip


def derive() -> dict[str, object]:
    n = len(CLOSES)
    close = [float(c) for c in CLOSES]
    high = [c + 1.0 for c in close]
    low = [c - 1.0 for c in close]
    tr = [high[0] - low[0]]
    for t in range(1, n):
        tr.append(max(high[t] - low[t], abs(high[t] - close[t - 1]), abs(low[t] - close[t - 1])))
    atr: list[float | None] = [None] * n
    atr[ATR_LENGTH - 1] = sum(tr[:ATR_LENGTH]) / ATR_LENGTH
    for t in range(ATR_LENGTH, n):
        prev = atr[t - 1]
        assert prev is not None
        atr[t] = (prev * (ATR_LENGTH - 1) + tr[t]) / ATR_LENGTH
    fu: list[float | None] = [None] * n
    fl: list[float | None] = [None] * n
    st: list[float | None] = [None] * n
    d: list[int | None] = [None] * n
    for t in range(n):
        a = atr[t]
        if a is None:
            continue
        hl2 = (high[t] + low[t]) / 2
        bu, bl = hl2 + FACTOR * a, hl2 - FACTOR * a
        pu, pl = fu[t - 1], fl[t - 1]
        if pu is None or pl is None:
            fu[t], fl[t] = bu, bl
        else:
            fu[t] = bu if (bu < pu or close[t - 1] > pu) else pu
            fl[t] = bl if (bl > pl or close[t - 1] < pl) else pl
        cu, cl = fu[t], fl[t]
        assert cu is not None
        assert cl is not None
        if atr[t - 1] is None:
            d[t] = -1
        elif st[t - 1] == fu[t - 1]:
            d[t] = 1 if close[t] > cu else -1
        else:
            d[t] = -1 if close[t] < cl else 1
        st[t] = cl if d[t] == 1 else cu
    return {
        "atr_length": ATR_LENGTH,
        "factor": FACTOR,
        "high": high,
        "low": low,
        "close": close,
        "atr": atr,
        "final_upper": fu,
        "final_lower": fl,
        "line": st,
        "direction": d,
    }


if __name__ == "__main__":
    out = derive()
    if "--write" in sys.argv:
        Path(__file__).with_name("supertrend_40bar.json").write_text(json.dumps(out, indent=1) + "\n")
    for t in range(len(CLOSES)):
        print(t, CLOSES[t], *(out[k][t] for k in ("atr", "final_upper", "final_lower", "line", "direction")))  # type: ignore[index]
