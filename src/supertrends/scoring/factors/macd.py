# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 3, MACD (Signal Engine Specification, Factor 3; PRD FR-3xx; S3-T02).

MACD(12, 26, 9) on daily closes comes from the snapshot. A tie is neither above nor below and adds
nothing:

    +-35  line above / below signal
    +-25  line above / below zero
    +-25  histogram rising / falling for 3 consecutive bars (`daily.macd_hist_run` is +1 / -1)
    +-15  bullish / bearish signal cross within the last `cross_lookback` (3) bars
    score = clip(sum, -100, 100)

Weekly MACD is reported as evidence; if the weekly line-vs-signal sign is the opposite of the daily
one, the score is multiplied by `weekly_disagree_multiplier` (0.75). A level (tied) daily or weekly
line is not a disagreement (PRD A-27). The cross window is checked as `bars - index <=
cross_lookback`, the as-of bar being bar 1 (PRD A-26). A null daily line or signal gives `missing`;
a null weekly MACD leaves the score unscaled and marks the factor `degraded`.

Snapshot inputs (dotted paths into `compute_snapshot`; `<period>` expands over `sma.periods`):

* `bars`
* `daily.macd.line`
* `daily.macd.signal`
* `daily.macd.hist`
* `daily.macd_hist_run`
* `daily.macd_cross`
* `weekly.macd.line`
* `weekly.macd.signal`
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from supertrends.scoring.factor import (
    SCORE_MAX,
    SCORE_MIN,
    EvidenceItem,
    FactorContext,
    FactorResult,
    Quality,
    ReasonTemplate,
    get_path,
)

FACTOR_ID = "macd"
OWNER_TASK = "S3-T02"
INPUT_PATHS: tuple[str, ...] = (
    "bars",
    "daily.macd.line",
    "daily.macd.signal",
    "daily.macd.hist",
    "daily.macd_hist_run",
    "daily.macd_cross",
    "weekly.macd.line",
    "weekly.macd.signal",
)

SIGNAL_POINTS = 35.0
ZERO_POINTS = 25.0
HIST_POINTS = 25.0
CROSS_POINTS = 15.0

LINE_VS_SIGNAL = ReasonTemplate(
    "macd.line_vs_signal", "MACD line {line} is {relation} the signal {signal}"
)
LINE_VS_ZERO = ReasonTemplate("macd.line_vs_zero", "MACD line {line} is {relation} zero")
HIST_RUN = ReasonTemplate("macd.hist_run", "MACD histogram {movement} for {bars} consecutive bars")
NO_HIST_RUN = ReasonTemplate("macd.no_hist_run", "MACD histogram has no {bars}-bar run")
CROSS = ReasonTemplate("macd.cross", "{name} MACD signal cross {ago} bars ago")
NO_CROSS = ReasonTemplate("macd.no_cross", "No MACD signal cross in the last {lookback} bars")
WEEKLY_LINE = ReasonTemplate(
    "macd.weekly_line", "Weekly MACD line {line} is {relation} the weekly signal {signal}"
)
WEEKLY_SIGNAL = ReasonTemplate("macd.weekly_signal", "Weekly MACD signal is {signal}")
WEEKLY_NA = ReasonTemplate("macd.weekly_na", "Weekly MACD is not available")
WEEKLY_DISAGREES = ReasonTemplate(
    "macd.weekly_disagrees",
    "Weekly MACD disagrees with daily, so the score is multiplied by {multiplier}",
)
WEEKLY_AGREES = ReasonTemplate(
    "macd.weekly_agrees", "Weekly MACD agrees with daily, so the score is unchanged"
)
WEEKLY_LEVEL = ReasonTemplate(
    "macd.weekly_level",
    "Weekly or daily MACD is level with its signal, so the score is unchanged",
)
MISSING = "MACD is not available (not enough history)"
HIST_RUN_BARS = 3  # "3 consecutive bars" in the rule; `daily.macd_hist_run` is computed for it


def _sign(a: float, b: float) -> int:
    return (a > b) - (a < b)


def _relation(sign: int) -> str:
    return "above" if sign > 0 else "below" if sign < 0 else "equal to"


def _optional(snapshot: Mapping[str, Any], path: str) -> float | None:
    value = get_path(snapshot, path)
    return None if value is None else float(value)


class _Macd:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        cfg = context.config.macd
        try:
            line = _optional(snapshot, "daily.macd.line")
            signal = _optional(snapshot, "daily.macd.signal")
            run = int(get_path(snapshot, "daily.macd_hist_run") or 0)
            cross = get_path(snapshot, "daily.macd_cross")
            bars = int(get_path(snapshot, "bars"))
            weekly_line = _optional(snapshot, "weekly.macd.line")
            weekly_signal = _optional(snapshot, "weekly.macd.signal")
        except KeyError:
            return FactorResult.missing(FACTOR_ID, reason=MISSING)
        if line is None or signal is None:
            return FactorResult.missing(FACTOR_ID, reason=MISSING)

        vs_signal = _sign(line, signal)
        vs_zero = _sign(line, 0.0)
        hist = (run > 0) - (run < 0)
        score = SIGNAL_POINTS * vs_signal + ZERO_POINTS * vs_zero + HIST_POINTS * hist
        evidence: list[EvidenceItem] = [
            LINE_VS_SIGNAL.evidence(
                "macd_line", line, "price", line=line, relation=_relation(vs_signal), signal=signal
            ),
            LINE_VS_ZERO.evidence(
                "macd_line_vs_zero", line, "price", line=line, relation=_relation(vs_zero)
            ),
        ]
        if hist == 0:
            evidence.append(NO_HIST_RUN.evidence("macd_hist_run", 0, "bars", bars=HIST_RUN_BARS))
        else:
            evidence.append(
                HIST_RUN.evidence(
                    "macd_hist_run",
                    hist,
                    "bars",
                    movement="rose" if hist > 0 else "fell",
                    bars=HIST_RUN_BARS,
                )
            )

        # `bars - index` counts the as-of bar as 1, so the window is bars - lookback..bars.
        if cross is not None and bars - int(cross["index"]) <= cfg.cross_lookback:
            direction = 1 if int(cross["direction"]) > 0 else -1
            score += CROSS_POINTS * direction
            evidence.append(
                CROSS.evidence(
                    "macd_cross",
                    direction,
                    "cross",
                    name="Bullish" if direction > 0 else "Bearish",
                    ago=bars - int(cross["index"]),
                )
            )
        else:
            evidence.append(
                NO_CROSS.evidence("macd_cross", 0, "cross", lookback=cfg.cross_lookback)
            )

        score = min(SCORE_MAX, max(SCORE_MIN, score))
        degraded = weekly_line is None or weekly_signal is None
        if weekly_line is None or weekly_signal is None:
            evidence.append(WEEKLY_NA.evidence("weekly_macd_line", None, "price"))
        else:
            weekly_vs_signal = _sign(weekly_line, weekly_signal)
            evidence.append(
                WEEKLY_LINE.evidence(
                    "weekly_macd_line",
                    weekly_line,
                    "price",
                    line=weekly_line,
                    relation=_relation(weekly_vs_signal),
                    signal=weekly_signal,
                )
            )
            evidence.append(
                WEEKLY_SIGNAL.evidence(
                    "weekly_macd_signal", weekly_signal, "price", signal=weekly_signal
                )
            )
            if vs_signal == 0 or weekly_vs_signal == 0:
                item = WEEKLY_LEVEL.evidence("weekly_macd_multiplier", 1.0, "multiplier")
            elif vs_signal != weekly_vs_signal:
                score *= cfg.weekly_disagree_multiplier
                item = WEEKLY_DISAGREES.evidence(
                    "weekly_macd_multiplier",
                    cfg.weekly_disagree_multiplier,
                    "multiplier",
                    multiplier=cfg.weekly_disagree_multiplier,
                )
            else:
                item = WEEKLY_AGREES.evidence("weekly_macd_multiplier", 1.0, "multiplier")
            evidence.append(item)

        return FactorResult(
            factor_id=FACTOR_ID,
            score=score,
            quality=Quality.DEGRADED if degraded else Quality.OK,
            evidence=tuple(evidence),
        )


FACTOR = _Macd()
