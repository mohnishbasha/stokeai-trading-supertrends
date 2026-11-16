# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Derivation of the TS-IND-133 hand-computed Ripster EMA Clouds fixture.

Plain-Python reference written straight from BUILD_PROMPT Factor 12 (it never imports
`supertrends`). Run `python tests/golden/handcomputed/ripster_clouds_derive.py --write` to
rebuild `ripster_clouds.json`. Per golden policy 5.5 item 6 the fixture is never regenerated
from the implementation; this script is the independent derivation, and a few rows are checked
by hand in tests/unit/indicators/test_ripster_clouds.py.

Design: short EMA pairs so the case fits in 60 bars: c1 3/4, c2 2/5, c3 8/12, c4 10/14,
c5 13/16, pullback lookback 3. High = close + 1 and low = close - 1, so hl2 = close. Bars 0-14
chop around 100 (closes inside the clouds, stack 0), 15-29 rally (stack flips to +1) with a held
dip into the c1 cloud at bar 23 and a failed one at bar 27, 30-47 fall (stack flips to -1), and
48-59 bounce into the c1 cloud from below (held bearish tests) before resuming down.
"""

import json
import sys
from pathlib import Path

CLOUDS = [(3, 4), (2, 5), (8, 12), (10, 14), (13, 16)]
LOOKBACK = 3
CLOSES = [
    100, 101, 100, 99, 100, 101, 100, 99, 100, 101,
    100, 99, 100, 101, 100, 102, 104, 106, 108, 110,
    112, 114, 116, 113, 117, 119, 121, 112, 120, 122,
    120, 117, 114, 111, 108, 105, 102, 99, 96, 93,
    90, 87, 84, 81, 78, 75, 72, 69, 71, 73,
    72, 70, 67, 64, 66, 63, 60, 57, 54, 51,
]  # fmt: skip

Num = float | None


def ema(src: list[float], n: int) -> list[Num]:
    """alpha = 2 / (n + 1), seeded with the SMA of the first n values (PRD 7.1)."""
    out: list[Num] = [None] * len(src)
    if len(src) < n:
        return out
    prev = sum(src[:n]) / n
    out[n - 1] = prev
    alpha = 2 / (n + 1)
    for t in range(n, len(src)):
        prev = prev + alpha * (src[t] - prev)
        out[t] = prev
    return out


def derive() -> dict[str, object]:  # noqa: C901, PLR0912
    n = len(CLOSES)
    close = [float(c) for c in CLOSES]
    high = [c + 1.0 for c in close]
    low = [c - 1.0 for c in close]
    src = [(h + lo) / 2 for h, lo in zip(high, low, strict=True)]
    clouds: list[dict[str, list[Num]]] = []
    for short, long in CLOUDS:
        es, el = ema(src, short), ema(src, long)
        top: list[Num] = [None] * n
        bot: list[Num] = [None] * n
        direction: list[Num] = [None] * n
        pos: list[Num] = [None] * n
        for t in range(n):
            s, lg = es[t], el[t]
            if s is None or lg is None:
                continue
            top[t], bot[t] = max(s, lg), min(s, lg)
            direction[t] = 1.0 if s > lg else -1.0
            pos[t] = 1.0 if close[t] > top[t] else -1.0 if close[t] < bot[t] else 0.0  # type: ignore[operator]
        clouds.append(
            {"ema_short": es, "ema_long": el, "top": top, "bot": bot, "direction": direction,
             "pos": pos}
        )  # fmt: skip
    c1, c2, c3 = clouds[0], clouds[1], clouds[2]
    stack: list[Num] = [None] * n
    for t in range(n):
        b2, t2, t3, b3 = c2["bot"][t], c2["top"][t], c3["top"][t], c3["bot"][t]
        if b2 is None or t2 is None or t3 is None or b3 is None:
            continue
        stack[t] = 1.0 if b2 > t3 else -1.0 if t2 < b3 else 0.0
    since: list[Num] = [None] * n
    count, prev = 0.0, None
    for t in range(n):
        s = stack[t]
        if s is None:
            continue
        count = count + 1.0 if s == prev else 0.0
        prev = s
        since[t] = None if s == 0 else count
    pullback: list[Num] = [None] * n
    for t in range(n):
        s = stack[t]
        if s is None or c1["top"][t] is None:
            continue
        window = range(max(0, t - LOOKBACK + 1), t + 1)
        value = 0.0
        if s == 1:
            tested = any(c1["top"][k] is not None and low[k] <= c1["top"][k] for k in window)  # type: ignore[operator]
            if tested and close[t] > c1["bot"][t]:  # type: ignore[operator]
                value = 1.0
        elif s == -1:
            tested = any(c1["bot"][k] is not None and high[k] >= c1["bot"][k] for k in window)  # type: ignore[operator]
            if tested and close[t] < c1["top"][t]:  # type: ignore[operator]
                value = -1.0
        pullback[t] = value
    return {
        "clouds": CLOUDS,
        "pullback_lookback": LOOKBACK,
        "high": high,
        "low": low,
        "close": close,
        "cloud": clouds,
        "stack": stack,
        "bars_since_stack_flip": since,
        "pullback": pullback,
    }


if __name__ == "__main__":
    data = derive()
    if "--write" in sys.argv:
        out = Path(__file__).with_name("ripster_clouds.json")
        out.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    else:
        for t in range(len(CLOSES)):
            c1 = data["cloud"][0]  # type: ignore[index]
            print(
                t, CLOSES[t], data["stack"][t], data["bars_since_stack_flip"][t],  # type: ignore[index]
                data["pullback"][t], c1["pos"][t], data["cloud"][2]["pos"][t],  # type: ignore[index]
            )  # fmt: skip
