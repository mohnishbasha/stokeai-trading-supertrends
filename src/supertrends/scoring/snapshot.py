# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Indicator snapshot of one ticker as of one date (S2-T09, ARCHITECTURE sections 4 and 5).

`compute_snapshot` is the `computing` step of a run for one ticker: it takes the ticker's bars
(daily, with 5-minute bars when supplied) and the scoring config, uses only bars up to and
including the as-of date, and returns a JSON-ready document:

* `daily` and `weekly`: the value at the last bar of every per-bar indicator (weekly bars are
  resampled in memory; the last weekly bar may be a partial week, ADR-033);
* `levels`: support and resistance, the 52-week high and low, and the Supertrend line as the
  invalidation level;
* `fib`: the last completed ZigZag leg with retracement and extension prices;
* `divergences`: confirmed divergence records, daily and weekly;
* `flow`: the order flow estimate and its data quality;
* `ripster`: the five EMA clouds, the stack, bias, pullback state and weekly direction (Factor 12).

Every parameter comes from the config (ADR-056 lists where the registry defaults apply instead).
The document is canonical: NaN is null (never 0), infinities are strings, floats are rounded to
10 significant digits with the same canonicalizer as the determinism hash, and
`snapshot_bytes` serializes with sorted keys. It is pure: no I/O, clock, or randomness. It lives
here, not under `indicators/`, because it reads the scoring config; it imports only the
indicators and the config model.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import numpy as np
from numpy.typing import NDArray

from supertrends.indicators.divergence import detect_all_divergences
from supertrends.indicators.fibonacci import EXTENSION_RATIOS, RETRACEMENT_RATIOS, fib_leg
from supertrends.indicators.flow import estimate_order_flow
from supertrends.indicators.levels import support_resistance
from supertrends.indicators.meanrev import bollinger, pct_b, zscore
from supertrends.indicators.momentum import hist_run, macd, macd_signal_cross, macd_weekly
from supertrends.indicators.primitives import atr, obv, resample_weekly, rsi, sma
from supertrends.indicators.registry import Bundle, canonical, round_significant
from supertrends.indicators.ripster_clouds import ripster_clouds, ripster_weekly_direction
from supertrends.indicators.supertrend import (
    bars_since_flip,
    distance_atr,
    supertrend,
    supertrend_weekly_direction,
)
from supertrends.indicators.trend import adx, cross_events, last_cross, sma_slope
from supertrends.indicators.volatility import (
    atr_pct,
    atr_pct_rank,
    bandwidth,
    bbw_rank,
    expansion,
    hv20,
    squeeze,
)
from supertrends.indicators.volume import (
    accumulation_distribution_days,
    cmf,
    obv_slope_sign,
    relative_volume,
    volume_oscillator,
)
from supertrends.scoring.config import ScoringConfig, config_hash

__all__ = [
    "NOT_SNAPSHOTTED",
    "SCHEMA_VERSION",
    "SNAPSHOT_COVERS",
    "compute_snapshot",
    "snapshot_bytes",
]

# Version 2 (S3-T01): added daily prev_close, high, low, close_lag_3, ret_5 and
# avg_dollar_volume_20d, the `ripster` block, and made `daily.sma_cross` SMA50 against SMA200.
SCHEMA_VERSION = 2
YEAR_BARS = 252
RET_BARS = 5
LAG_BARS = 3
DOLLAR_VOLUME_BARS = 20

FloatArray = NDArray[np.float64]

# Registered per-bar indicators (series entries of indicators.registry) and where the snapshot
# carries them. A test fails when a registered series indicator is in neither mapping.
SNAPSHOT_COVERS: dict[str, str] = {
    "accumulation_distribution_days": "daily.acc_dist",
    "adx": "daily.adx",
    "atr": "daily.atr",
    "atr_pct": "daily.atr_pct",
    "atr_pct_rank": "daily.atr_pct_rank",
    "bandwidth": "daily.bandwidth",
    "bars_since_flip": "daily.bars_since_flip",
    "bbw_rank": "daily.bbw_rank",
    "bollinger": "daily.bollinger",
    "cmf": "daily.cmf",
    "bars_since_stack_flip": "ripster.bars_since_stack_flip",
    "cloud_stack": "ripster.stack",
    "cross_events": "daily.sma_cross",
    "distance_atr": "daily.distance_atr",
    "divergence_series": "divergences",
    "estimate_order_flow": "flow",
    "expansion": "daily.expansion",
    "hist_run": "daily.macd_hist_run",
    "hv20": "daily.hv20",
    "macd": "daily.macd",
    "macd_weekly": "weekly.macd",
    "obv": "daily.obv",
    "obv_slope_sign": "daily.obv_slope_sign",
    "pct_b": "daily.pct_b",
    "relative_volume": "daily.relative_volume",
    "ripster_clouds": "ripster.clouds",
    "ripster_pullback": "ripster.pullback",
    "ripster_weekly_direction": "ripster.dir_w",
    "rsi": "daily.rsi",
    "sma": "daily.sma_<period>",
    "sma_slope": "daily.sma_slope_<period>",
    "sma_stack": "daily.sma_<period>",
    "squeeze": "daily.squeeze",
    "supertrend": "daily.supertrend",
    "supertrend_weekly_direction": "weekly.supertrend_direction",
    "volume_oscillator": "daily.volume_oscillator",
    "zscore": "daily.zscore",
}
NOT_SNAPSHOTTED: dict[str, str] = {
    "ema": "building block of MACD; not a decision input on its own",
    "ema_cloud": "building block of ripster_clouds",
    "linreg_slope": "building block of the OBV slope sign",
    "percentile_rank": "building block of the BBW and ATR% ranks",
    "pivot_masks": "building block of the divergence and level detectors",
    "rma": "building block of ATR, RSI and ADX",
    "split_volume": "building block of the order flow estimate",
    "stdev": "building block of Bollinger, z-score and HV20",
    "true_range": "building block of ATR",
    "zigzag_threshold": "building block of the Fibonacci leg (the leg itself is in fib)",
}


def _last(values: NDArray[Any]) -> float:
    return float(values[-1])


def _lagged(values: FloatArray, lag: int) -> float:
    """The value `lag` bars before the last bar; NaN (null) when the history is shorter."""
    return float(values[-1 - lag]) if len(values) > lag else float("nan")


def _return(close: FloatArray, bars: int) -> float:
    """`close[t] / close[t - bars] - 1`; NaN when there are fewer than `bars + 1` closes."""
    base = _lagged(close, bars)
    return float(close[-1] / base - 1.0) if base > 0 else float("nan")


def _avg_dollar_volume(close: FloatArray, volume: FloatArray, bars: int) -> float:
    """Mean of `close * volume` over the last `bars` sessions; NaN with fewer bars."""
    if len(close) < bars:
        return float("nan")
    return float((close[-bars:] * volume[-bars:]).mean())


def _daily(b: Bundle, cfg: ScoringConfig) -> dict[str, Any]:
    close, high, low, volume = b.close, b.high, b.low, b.volume
    vol = cfg.volatility
    st = supertrend(high, low, close, cfg.supertrend.atr_length, cfg.supertrend.factor)
    m = macd(close, cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    bb = bollinger(close, vol.bb_length, vol.bb_mult)
    ad = adx(high, low, close, cfg.regime.adx_length)
    days = accumulation_distribution_days(close, volume)
    bbw = bbw_rank(close, vol.bb_length, vol.bb_mult)
    bw = bandwidth(close, vol.bb_length, vol.bb_mult)
    out: dict[str, Any] = {
        "close": _last(close),
        "high": _last(high),
        "low": _last(low),
        "volume": _last(volume),
        "prev_close": _lagged(close, 1),
        "close_lag_3": _lagged(close, LAG_BARS),
        "ret_5": _return(close, RET_BARS),
        "avg_dollar_volume_20d": _avg_dollar_volume(close, volume, DOLLAR_VOLUME_BARS),
    }
    averages = {p: sma(close, p) for p in cfg.sma.periods}
    for p, values in averages.items():
        out[f"sma_{p}"] = _last(values)
        out[f"sma_slope_{p}"] = _last(sma_slope(values, cfg.sma.slope_bars))
    if len(cfg.sma.periods) >= 3:
        mid, slow = (averages[p] for p in cfg.sma.periods[1:3])
        out["sma_cross"] = last_cross(mid, slow, cfg.sma.cross_lookback)
        out["sma_cross_events"] = int(cross_events(mid, slow)[-1])
    out |= {
        "rsi": _last(rsi(close, cfg.mean_reversion.rsi_length)),
        "atr": _last(atr(high, low, close, vol.atr_length)),
        "atr_pct": _last(atr_pct(high, low, close, vol.atr_length)),
        "atr_pct_rank": _last(atr_pct_rank(high, low, close, vol.atr_length)),
        "obv": _last(obv(close, volume)),
        "supertrend": {
            "line": _last(st.line),
            "direction": _last(st.direction),
            "atr": _last(st.atr),
            "final_upper": _last(st.final_upper),
            "final_lower": _last(st.final_lower),
        },
        "bars_since_flip": _last(bars_since_flip(st.direction)),
        "distance_atr": _last(distance_atr(close, st.line, st.atr)),
        "adx": {"adx": _last(ad.adx), "plus_di": _last(ad.plus_di), "minus_di": _last(ad.minus_di)},
        "macd": {"line": _last(m.line), "signal": _last(m.signal), "hist": _last(m.hist)},
        "macd_cross": macd_signal_cross(m.line, m.signal, cfg.macd.cross_lookback),
        "macd_hist_run": _last(hist_run(m.hist, cfg.macd.cross_lookback)),
        "bollinger": {
            "middle": _last(bb.middle),
            "upper": _last(bb.upper),
            "lower": _last(bb.lower),
        },
        "pct_b": _last(pct_b(close, vol.bb_length, vol.bb_mult)),
        "zscore": _last(zscore(close, cfg.mean_reversion.window)),
        "bandwidth": _last(bw),
        "bbw_rank": _last(bbw),
        "squeeze": _last(squeeze(bbw, vol.squeeze_rank)),
        "expansion": _last(expansion(bbw, bw, vol.expansion_rank)),
        "hv20": _last(hv20(close)),
        "volume_oscillator": _last(
            volume_oscillator(volume, cfg.volume.osc_short, cfg.volume.osc_long)
        ),
        "relative_volume": _last(relative_volume(volume)),
        "obv_slope_sign": _last(obv_slope_sign(close, volume, cfg.volume.obv_slope_bars)),
        "cmf": _last(cmf(high, low, close, volume, cfg.flow.cmf_length)),
        "acc_dist": {
            "accumulation": _last(days.accumulation),
            "distribution": _last(days.distribution),
        },
    }
    return out


def _weekly(b: Bundle, cfg: ScoringConfig) -> dict[str, Any]:
    weekly = resample_weekly(b.dates, b.open, b.high, b.low, b.close, b.volume)
    st = supertrend(
        weekly.high, weekly.low, weekly.close, cfg.supertrend.atr_length, cfg.supertrend.factor
    )
    mw = macd_weekly(b.dates, b.close, cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    out: dict[str, Any] = {
        "weeks": len(weekly.close),
        "close": _last(weekly.close),
        "rsi": _last(rsi(weekly.close, cfg.mean_reversion.rsi_length)),
        "atr": _last(atr(weekly.high, weekly.low, weekly.close, cfg.volatility.atr_length)),
        "supertrend": {"line": _last(st.line), "direction": _last(st.direction)},
        "supertrend_direction": _last(
            supertrend_weekly_direction(
                b.dates,
                b.open,
                b.high,
                b.low,
                b.close,
                b.volume,
                cfg.supertrend.atr_length,
                cfg.supertrend.factor,
            )
        ),
        "macd": {"line": _last(mw.line), "signal": _last(mw.signal), "hist": _last(mw.hist)},
    }
    for p in cfg.sma.periods:
        out[f"sma_{p}"] = _last(sma(weekly.close, p))
    return out


def _ripster(b: Bundle, cfg: ScoringConfig) -> dict[str, Any]:
    """The Factor 12 inputs at the last bar: five clouds, stack, bias, flip count, pullback."""
    rc = cfg.ripster
    res = ripster_clouds(
        b.high, b.low, b.close, rc.clouds.pairs(), pullback_lookback=rc.pullback_lookback_bars
    )
    clouds = {
        f"c{i}": {
            "top": _last(c.top),
            "bot": _last(c.bot),
            "dir": _last(c.direction),
            "pos": _last(c.pos),
        }
        for i, c in enumerate(res.clouds, start=1)
    }
    c2, c3 = res.clouds[1], res.clouds[2]
    short, long = rc.clouds.c3
    weekly_dir = ripster_weekly_direction(
        b.dates, b.open, b.high, b.low, b.close, b.volume, short, long
    )
    return {
        "bias": _last(c3.pos),
        "stack": _last(res.stack),
        "bars_since_stack_flip": _last(res.bars_since_stack_flip),
        "pullback": _last(res.pullback),
        "c2_dir": _last(c2.direction),
        "c3_dir": _last(c3.direction),
        "c3_top": _last(c3.top),
        "c3_bot": _last(c3.bot),
        "dir_w": _last(weekly_dir),
        "clouds": clouds,
    }


def _levels(b: Bundle, cfg: ScoringConfig, st_line: float) -> dict[str, Any]:
    lv = cfg.levels
    year_high, year_low = b.high[-YEAR_BARS:], b.low[-YEAR_BARS:]
    sr = support_resistance(
        b.high,
        b.low,
        b.close,
        b.volume,
        width=lv.pivot_width,
        lookback=lv.lookback_bars,
        atr_period=cfg.volatility.atr_length,
        cluster_atr=lv.cluster_atr,
        year_bars=YEAR_BARS,
        rv_min=lv.breakout_rel_volume,
    )
    return {
        "high_52w": float(np.nanmax(year_high)),
        "low_52w": float(np.nanmin(year_low)),
        "invalidation": st_line,
        "support_resistance": sr,
    }


def _fib(b: Bundle, cfg: ScoringConfig) -> dict[str, Any]:
    fb = cfg.fibonacci
    leg = fib_leg(
        b.high,
        b.low,
        b.close,
        lookback=fb.lookback_bars,
        min_pct=fb.min_reversal_pct,
        atr_mult=fb.min_reversal_atr,
        atr_period=cfg.volatility.atr_length,
    )
    if leg is None:
        return {"leg": None, "retracements": [], "extensions": []}
    return {
        "leg": leg,
        "retracements": [
            {"ratio": r, "price": p}
            for r, p in zip(RETRACEMENT_RATIOS, leg.retracements, strict=True)
        ],
        "extensions": [
            {"ratio": r, "price": p} for r, p in zip(EXTENSION_RATIOS, leg.extensions, strict=True)
        ],
    }


def _divergences(b: Bundle, cfg: ScoringConfig) -> dict[str, Any]:
    dv = cfg.divergence
    weekly = resample_weekly(b.dates, b.open, b.high, b.low, b.close, b.volume)
    return {
        "daily": detect_all_divergences(
            b.high,
            b.low,
            b.close,
            b.volume,
            width=dv.pivot_width_daily,
            lookback=dv.window_bars,
            recency=dv.recency_bars,
            as_of=len(b) - 1,
        ),
        "weekly": detect_all_divergences(
            weekly.high,
            weekly.low,
            weekly.close,
            weekly.volume,
            timeframe="weekly",
            width=dv.pivot_width_weekly,
            lookback=dv.window_bars,
            recency=dv.recency_bars,
            as_of=len(weekly.close) - 1,
        ),
    }


def _flow(b: Bundle, cfg: ScoringConfig) -> dict[str, Any]:
    intraday: dict[str, Any] = {}
    if len(b.bar_start):
        intraday = {
            "bar_start": b.bar_start,
            "high": b.i_high,
            "low": b.i_low,
            "close": b.i_close,
            "volume": b.i_volume,
        }
    res = estimate_order_flow(
        b.dates,
        b.high,
        b.low,
        b.close,
        b.volume,
        **intraday,
        window=cfg.flow.window_sessions,
        min_intraday_sessions=cfg.flow.min_sessions_for_intraday,
    )
    return {
        "delta_pct": _last(res.delta_pct),
        "delta_pct_10": res.delta_pct_10,
        "quality": res.quality,
        "daily_fallback": res.daily_fallback,
        "intraday_sessions": res.intraday_sessions,
    }


def compute_snapshot(bundle: Bundle, cfg: ScoringConfig, as_of: date) -> dict[str, Any]:
    """Canonical indicator snapshot using only the bars dated on or before `as_of`.

    `bundle` may hold later bars (they are dropped before any computation, so the result is
    byte-identical with or without them). If `as_of` is not a session, the last earlier bar is
    the as-of bar and `bar_date` says which. Raises ValueError when no bar is on or before
    `as_of`. Indicators still in warm-up are null.
    """
    n = int(np.searchsorted(bundle.dates, np.datetime64(as_of), side="right"))
    if n == 0:
        msg = f"no bars on or before {as_of.isoformat()}"
        raise ValueError(msg)
    b = bundle.head(n)
    daily = _daily(b, cfg)
    doc = {
        "schema": SCHEMA_VERSION,
        "as_of": as_of.isoformat(),
        "bar_date": str(b.dates[-1]),
        "bars": n,
        "config_hash": config_hash(cfg),
        "daily": daily,
        "weekly": _weekly(b, cfg),
        "levels": _levels(b, cfg, daily["supertrend"]["line"]),
        "fib": _fib(b, cfg),
        "divergences": _divergences(b, cfg),
        "flow": _flow(b, cfg),
        "ripster": _ripster(b, cfg),
    }
    result: dict[str, Any] = round_significant(canonical(doc))
    return result


def snapshot_bytes(doc: dict[str, Any]) -> bytes:
    """Deterministic serialization of a snapshot: sorted keys, compact, ASCII."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
