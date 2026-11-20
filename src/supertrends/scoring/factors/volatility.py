# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor 8, Volatility squeeze and expansion (Signal Engine Specification; owner task S3-T03).

Rules (BUILD_PROMPT Factor 8; PRD FR-311; scoring.yaml `volatility`):

    squeeze   = bbw_rank < squeeze_rank (strict)  -> +30 * st_dir_d
    expansion = bbw_rank > expansion_rank and bbw rising 3 bars (snapshot flag), and close moved
                in the st_dir_d direction over 3 bars -> +20 * st_dir_d
    score     = that sum, times 0.5 if atr_pct_rank > extreme_atr_rank

`expected_1d_move = atr14` is risk evidence on every card.

Snapshot inputs (dotted paths into `compute_snapshot`; `<period>` expands over `sma.periods`):

* `daily.squeeze`
* `daily.expansion`
* `daily.atr_pct_rank`
* `daily.bbw_rank`
* `daily.supertrend.direction`
* `daily.close`
* `daily.close_lag_3`
* `daily.atr`
* `daily.atr_pct`
* `daily.hv20`
* `daily.bandwidth`
"""

from collections.abc import Mapping
from typing import Any

from supertrends.scoring.factor import (
    FactorContext,
    FactorResult,
    Quality,
    ReasonTemplate,
    get_path,
)
from supertrends.scoring.factors._values import num, sign

FACTOR_ID = "volatility"
OWNER_TASK = "S3-T03"
INPUT_PATHS: tuple[str, ...] = (
    "daily.squeeze",
    "daily.expansion",
    "daily.atr_pct_rank",
    "daily.bbw_rank",
    "daily.supertrend.direction",
    "daily.close",
    "daily.close_lag_3",
    "daily.atr",
    "daily.atr_pct",
    "daily.hv20",
    "daily.bandwidth",
)

SQUEEZE_POINTS = 30.0
EXPANSION_POINTS = 20.0
EXTREME_MULTIPLIER = 0.5

_NO_DATA = ReasonTemplate("vol_no_data", "Bollinger band width rank or Supertrend is not available")
_SQUEEZE = ReasonTemplate(
    "vol_squeeze", "Band width rank {rank} is below {limit}: volatility is compressed"
)
_EXPANSION = ReasonTemplate(
    "vol_expansion",
    "Band width rank {rank} is above {limit} and rising, and the close moved with the trend",
)
_EXPANSION_AGAINST = ReasonTemplate(
    "vol_expansion_against",
    "Band width rank {rank} is above {limit} and rising, but the close moved against the trend",
)
_QUIET = ReasonTemplate("vol_none", "Band width rank {rank} is neither a squeeze nor an expansion")
_EXTREME = ReasonTemplate(
    "vol_extreme", "ATR rank {rank} is above {limit}: the score is halved in extreme volatility"
)
_MOVE = ReasonTemplate("vol_move", "Expected one-day move is {atr} (ATR 14)")
_ATR_PCT = ReasonTemplate("vol_atr_pct", "ATR is {pct} percent of the close")
_HV = ReasonTemplate("vol_hv20", "20-day historical volatility is {hv} percent annualized")
_BW = ReasonTemplate("vol_bandwidth", "Bollinger band width is {bw} percent of the average")
_ATR_RANK_NA = ReasonTemplate("vol_atr_rank_na", "ATR percentile rank is not available")


class _Volatility:
    id = FACTOR_ID
    input_paths = INPUT_PATHS

    def compute(self, snapshot: Mapping[str, Any], context: FactorContext) -> FactorResult:
        cfg = context.config.volatility
        direction = sign(num(snapshot, "daily.supertrend.direction"))
        rank = num(snapshot, "daily.bbw_rank")
        if direction == 0 or rank is None:
            return FactorResult.missing(FACTOR_ID, reason=_NO_DATA.render())
        close = num(snapshot, "daily.close")
        lag = num(snapshot, "daily.close_lag_3")
        atr = num(snapshot, "daily.atr")
        atr_rank = num(snapshot, "daily.atr_pct_rank")
        degraded = atr is None or atr_rank is None
        score = 0.0
        evidence = []
        if rank < cfg.squeeze_rank:
            score += SQUEEZE_POINTS * direction
            evidence.append(
                _SQUEEZE.evidence("squeeze", True, "flag", rank=rank, limit=cfg.squeeze_rank)
            )
        elif rank > cfg.expansion_rank and bool(get_path(snapshot, "daily.expansion")):
            moved = close is not None and lag is not None and direction * (close - lag) > 0
            template = _EXPANSION if moved else _EXPANSION_AGAINST
            if moved:
                score += EXPANSION_POINTS * direction
            evidence.append(
                template.evidence("expansion", moved, "flag", rank=rank, limit=cfg.expansion_rank)
            )
        else:
            evidence.append(_QUIET.evidence("bbw_rank", rank, "percentile", rank=rank))
        if atr_rank is not None and atr_rank > cfg.extreme_atr_rank:
            score *= EXTREME_MULTIPLIER
            evidence.append(
                _EXTREME.evidence(
                    "atr_pct_rank",
                    atr_rank,
                    "percentile",
                    rank=atr_rank,
                    limit=cfg.extreme_atr_rank,
                )
            )
        elif atr_rank is None:
            evidence.append(_ATR_RANK_NA.evidence("atr_pct_rank", None, "percentile"))
        if atr is not None:
            evidence.append(_MOVE.evidence("expected_1d_move", atr, "price", atr=atr))
        atr_pct = num(snapshot, "daily.atr_pct")
        if atr_pct is not None:
            evidence.append(
                _ATR_PCT.evidence("atr_pct", atr_pct * 100, "percent", pct=atr_pct * 100)
            )
        hv = num(snapshot, "daily.hv20")
        if hv is not None:
            evidence.append(_HV.evidence("hv20", hv * 100, "percent", hv=hv * 100))
        bw = num(snapshot, "daily.bandwidth")
        if bw is not None:
            evidence.append(_BW.evidence("bandwidth", bw * 100, "percent", bw=bw * 100))
        return FactorResult(
            factor_id=FACTOR_ID,
            score=score + 0.0,
            quality=Quality.DEGRADED if degraded else Quality.OK,
            evidence=tuple(evidence),
        )


FACTOR = _Volatility()
