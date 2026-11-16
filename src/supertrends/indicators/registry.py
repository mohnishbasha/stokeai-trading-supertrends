# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Registry of every public indicator, for the no-look-ahead and determinism harness (S2-T08).

TEST_PLAN sections 6 and 7; ARCHITECTURE section 2 ("every public function is registered with the
no-look-ahead harness"). The registry lives here (not under tests/) so that the harness, the
determinism hash, the benchmark and the indicator snapshot task (S2-T09) share one list of what
"all indicators" means. It is pure: no I/O, clock, randomness or globals.

Each `Entry` has an adapter that calls the indicator on a `Bundle` (daily OHLCV, plus 5-minute
bars for order flow) and returns comparable output:

* `series`: dict of float64 arrays aligned to the daily index (per-bar indicators). The value at
  index i may use bars <= i only; `confirm_lag` is the confirmation delay (5 for pivot masks), so
  indexes below `m - confirm_lag` must not change when only the first `m` bars are given.
* `asof`: `asof(bundle, t)` is the result as of bar t (as-of-last-bar records such as `fib_leg`).
  The bundle may hold bars after t. Functions with an `as_of` argument get it; the others are
  given `bundle.head(t + 1)`, and functions that return history filter it to what is known at t.

An entry may have both (`estimate_order_flow`). `EXEMPT` lists public names that are not
indicators (records, enums, protocols, constants), each with a reason. A test fails when a name in
`supertrends.indicators.__all__` is neither registered nor exempt.
"""

from __future__ import annotations

import dataclasses
import enum
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from supertrends.indicators.divergence import (
    detect_all_divergences,
    detect_divergences,
    detect_weekly_divergences,
    divergence_records,
    divergence_series,
)
from supertrends.indicators.fibonacci import fib_leg, holding, near
from supertrends.indicators.flow import estimate_order_flow, split_volume
from supertrends.indicators.levels import recency_weight, support_resistance
from supertrends.indicators.meanrev import bollinger, pct_b, zscore
from supertrends.indicators.momentum import hist_run, macd, macd_signal_cross, macd_weekly
from supertrends.indicators.primitives import (
    atr,
    ema,
    linreg_slope,
    obv,
    percentile_rank,
    pivot_confirmation_bar,
    pivot_masks,
    pivots,
    resample_weekly,
    rma,
    rsi,
    sma,
    stdev,
    true_range,
    zigzag,
    zigzag_threshold,
)
from supertrends.indicators.supertrend import (
    bars_since_flip,
    distance_atr,
    supertrend,
    supertrend_weekly_direction,
)
from supertrends.indicators.trend import adx, cross_events, last_cross, sma_slope, sma_stack
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

FloatArray = NDArray[np.float64]
SeriesAdapter = Callable[["Bundle"], dict[str, FloatArray]]
AsofAdapter = Callable[["Bundle", int], object]

__all__ = [
    "EXEMPT",
    "REGISTRY",
    "SIGNIFICANT_DIGITS",
    "Bundle",
    "Entry",
    "canonical",
    "compute_all",
    "round_significant",
    "unregistered",
]

PIVOT_WIDTH = 5


@dataclass(frozen=True)
class Bundle:
    """Daily OHLCV plus optional 5-minute bars, as numpy arrays.

    `dates` is datetime64[D] ascending. The 5-minute bars (`bar_start` as session-local
    datetime64[m], OHLCV) are sorted; `i_day[k]` is the daily index of the session of bar k. All
    intraday arrays may be empty.
    """

    dates: NDArray[np.datetime64]
    open: FloatArray
    high: FloatArray
    low: FloatArray
    close: FloatArray
    volume: FloatArray
    i_day: NDArray[np.int64]
    bar_start: NDArray[np.datetime64]
    i_high: FloatArray
    i_low: FloatArray
    i_close: FloatArray
    i_volume: FloatArray

    def __len__(self) -> int:
        return len(self.close)

    def head(self, m: int) -> Bundle:
        """The first `m` daily bars and the 5-minute bars of those sessions."""
        k = int(np.searchsorted(self.i_day, m))
        return Bundle(
            self.dates[:m],
            self.open[:m],
            self.high[:m],
            self.low[:m],
            self.close[:m],
            self.volume[:m],
            self.i_day[:k],
            self.bar_start[:k],
            self.i_high[:k],
            self.i_low[:k],
            self.i_close[:k],
            self.i_volume[:k],
        )

    def with_tail(self, m: int, other: Bundle) -> Bundle:
        """This bundle with every bar after the first `m` replaced by `other`'s bars.

        Dates and 5-minute bar times are kept (so the result stays sorted); prices and volumes
        come from `other`, which must have the same shape. Used to perturb the future.
        """
        if len(other) != len(self) or len(other.i_day) != len(self.i_day):
            msg = "the other bundle must have the same shape"
            raise ValueError(msg)
        k = int(np.searchsorted(self.i_day, m))

        def mix(mine: FloatArray, theirs: FloatArray, cut: int) -> FloatArray:
            return np.concatenate([mine[:cut], theirs[cut:]])

        return Bundle(
            self.dates,
            mix(self.open, other.open, m),
            mix(self.high, other.high, m),
            mix(self.low, other.low, m),
            mix(self.close, other.close, m),
            mix(self.volume, other.volume, m),
            self.i_day,
            self.bar_start,
            mix(self.i_high, other.i_high, k),
            mix(self.i_low, other.i_low, k),
            mix(self.i_close, other.i_close, k),
            mix(self.i_volume, other.i_volume, k),
        )


@dataclass(frozen=True)
class Entry:
    """One registered indicator: adapters, and the confirmation lag of its `series` output."""

    name: str
    series: SeriesAdapter | None = None
    asof: AsofAdapter | None = None
    confirm_lag: int = 0

    @property
    def kind(self) -> str:
        """`series`, `asof`, or `both`."""
        return "both" if self.series and self.asof else "series" if self.series else "asof"


# --- canonical form -------------------------------------------------------------------------


def _float(x: float) -> float | str | None:
    """NaN becomes None and infinities strings, so the result is strict JSON."""
    if math.isnan(x):
        return None
    return x if math.isfinite(x) else ("inf" if x > 0 else "-inf")


def _array(a: NDArray[Any]) -> list[Any]:
    if a.dtype.kind == "M":
        return [str(x) for x in a]
    if a.dtype.kind == "f":
        values: list[Any] = a.astype(np.float64).tolist()
        for i in np.flatnonzero(~np.isfinite(a)).tolist():
            values[i] = _float(values[i])
        return values
    return a.tolist()  # type: ignore[no-any-return]


def canonical(obj: Any) -> object:  # noqa: PLR0911
    """JSON-safe, order-stable form of an indicator result.

    Arrays become lists (NaN null, infinities strings, datetimes ISO strings), dataclasses and
    dicts become dicts, tuples lists, enums their values, numpy scalars Python scalars.
    """
    if obj is None or isinstance(obj, bool | str):
        return obj
    if isinstance(obj, enum.Enum):
        return canonical(obj.value)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, int | np.integer):
        return int(obj)
    if isinstance(obj, float | np.floating):
        return _float(float(obj))
    if isinstance(obj, np.datetime64):
        return str(obj)
    if isinstance(obj, np.ndarray):
        return _array(obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: canonical(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): canonical(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [canonical(v) for v in obj]
    msg = f"cannot canonicalize {type(obj).__name__}"
    raise TypeError(msg)


SIGNIFICANT_DIGITS = 10  # indicator floats are stored and hashed to 10 digits (ADR-056)


def round_significant(obj: Any) -> Any:
    """Round every float in a canonical structure to `SIGNIFICANT_DIGITS` significant digits.

    libm and BLAS differ by a few ulps across platforms, so the last bits of a double are not
    reproducible; ten digits are (ADR-056). Dicts and lists are rebuilt, other values pass through.
    """
    if isinstance(obj, float):
        return float(f"{obj:.{SIGNIFICANT_DIGITS - 1}e}")
    if isinstance(obj, dict):
        return {k: round_significant(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_significant(v) for v in obj]
    return obj


# --- adapters -------------------------------------------------------------------------------


def _arrays(obj: object) -> dict[str, FloatArray]:
    """Fields of a dataclass of arrays, as float64."""
    return {
        f.name: np.asarray(getattr(obj, f.name), dtype=np.float64)
        for f in dataclasses.fields(obj)  # type: ignore[arg-type]
    }


def _one(values: NDArray[Any]) -> dict[str, FloatArray]:
    return {"out": np.asarray(values, dtype=np.float64)}


def _prev_close(b: Bundle) -> FloatArray:
    return np.concatenate([b.close[:1], b.close[:-1]])


def _st(b: Bundle) -> Any:
    return supertrend(b.high, b.low, b.close, 10, 3.0)


def _flow_args(b: Bundle) -> tuple[Any, ...]:
    """Daily and (when present) 5-minute arguments of `estimate_order_flow`."""
    daily = (b.dates, b.high, b.low, b.close, b.volume)
    if len(b.bar_start) == 0:
        return daily
    return (*daily, b.bar_start, b.i_high, b.i_low, b.i_close, b.i_volume)


def _flow_series(b: Bundle) -> dict[str, FloatArray]:
    res = estimate_order_flow(*_flow_args(b))
    return {"buy": res.buy, "sell": res.sell, "delta": res.delta, "delta_pct": res.delta_pct}


def _flow_asof(b: Bundle, t: int) -> object:
    res = estimate_order_flow(*_flow_args(b.head(t + 1)))
    return {
        "delta_pct_10": res.delta_pct_10,
        "quality": res.quality,
        "daily_fallback": res.daily_fallback,
        "intraday_sessions": res.intraday_sessions,
    }


def _resample_asof(b: Bundle, t: int) -> object:
    """Completed weeks from whatever was given, and the partial week from bars <= t."""
    whole = resample_weekly(b.dates, b.open, b.high, b.low, b.close, b.volume)
    done = int(whole.week_index[t])
    h = b.head(t + 1)
    part = resample_weekly(h.dates, h.open, h.high, h.low, h.close, h.volume)
    fields = ("week_ending", "open", "high", "low", "close", "volume", "sessions")
    return {
        "completed": {f: getattr(whole, f)[:done] for f in fields},
        "partial": {f: getattr(part, f)[-1:] for f in fields},
        "week_index": whole.week_index[: t + 1],
    }


def _zigzag_asof(b: Bundle, t: int) -> object:
    thr = zigzag_threshold(atr(b.high, b.low, b.close, 14), b.close)
    swings = zigzag(b.close, thr).confirmed
    return [s for s in swings if s.confirmed_at is not None and s.confirmed_at <= t]


def _weekly_div_asof(b: Bundle, t: int) -> object:
    h = b.head(t + 1)
    weekly = resample_weekly(h.dates, h.open, h.high, h.low, h.close, h.volume)
    return detect_weekly_divergences(weekly)


def _div_series(b: Bundle) -> dict[str, FloatArray]:
    return _arrays(divergence_series(b.high, b.low, rsi(b.close, 14)))


def _scalars_at(b: Bundle, t: int) -> tuple[float, float, float, float]:
    """close[t], close[t-1], sma20[t] and atr14[t] from the bars up to t."""
    h = b.head(t + 1)
    c = h.close
    return (
        float(c[-1]),
        float(c[-2]),
        float(sma(c, 20)[-1]),
        float(atr(h.high, h.low, c, 14)[-1]),
    )


def _near_asof(b: Bundle, t: int) -> object:
    close, _, level, a = _scalars_at(b, t)
    return near(close, level, a)


def _holding_asof(b: Bundle, t: int) -> object:
    close, prev, level, a = _scalars_at(b, t)
    direction = 1 if close >= prev else -1
    return holding(
        direction, close, prev, float(b.low[t] if direction > 0 else b.high[t]), level, a
    )


def _entries() -> list[Entry]:
    series: dict[str, SeriesAdapter] = {
        "sma": lambda b: _one(sma(b.close, 20)),
        "stdev": lambda b: _one(stdev(b.close, 20)),
        "ema": lambda b: _one(ema(b.close, 20)),
        "rma": lambda b: _one(rma(b.close, 14)),
        "true_range": lambda b: _one(true_range(b.high, b.low, b.close)),
        "atr": lambda b: _one(atr(b.high, b.low, b.close, 14)),
        "rsi": lambda b: _one(rsi(b.close, 14)),
        "obv": lambda b: _one(obv(b.close, b.volume)),
        "percentile_rank": lambda b: _one(percentile_rank(b.close, 50)),
        "linreg_slope": lambda b: _one(linreg_slope(b.close, 10)),
        "zigzag_threshold": lambda b: _one(
            zigzag_threshold(atr(b.high, b.low, b.close, 14), b.close)
        ),
        "supertrend": lambda b: _arrays(_st(b)),
        "bars_since_flip": lambda b: _one(bars_since_flip(_st(b).direction)),
        "distance_atr": lambda b: _one(distance_atr(b.close, _st(b).line, _st(b).atr)),
        "supertrend_weekly_direction": lambda b: _one(
            supertrend_weekly_direction(b.dates, b.open, b.high, b.low, b.close, b.volume)
        ),
        "sma_stack": lambda b: _arrays(sma_stack(b.close)),
        "sma_slope": lambda b: _one(sma_slope(sma(b.close, 20), 5)),
        "cross_events": lambda b: _one(cross_events(sma(b.close, 20), sma(b.close, 50))),
        "adx": lambda b: _arrays(adx(b.high, b.low, b.close, 14)),
        "macd": lambda b: _arrays(macd(b.close)),
        "macd_weekly": lambda b: _arrays(macd_weekly(b.dates, b.close)),
        "hist_run": lambda b: _one(hist_run(macd(b.close).hist, 3)),
        "bollinger": lambda b: _arrays(bollinger(b.close, 20, 2.0)),
        "pct_b": lambda b: _one(pct_b(b.close, 20, 2.0)),
        "zscore": lambda b: _one(zscore(b.close, 20)),
        "bandwidth": lambda b: _one(bandwidth(b.close, 20, 2.0)),
        "bbw_rank": lambda b: _one(bbw_rank(b.close, 20, 2.0, 126)),
        "atr_pct": lambda b: _one(atr_pct(b.high, b.low, b.close, 14)),
        "atr_pct_rank": lambda b: _one(atr_pct_rank(b.high, b.low, b.close, 14, 252)),
        "hv20": lambda b: _one(hv20(b.close, 20, 252)),
        "squeeze": lambda b: _one(squeeze(bbw_rank(b.close, 20, 2.0, 126), 15.0)),
        "expansion": lambda b: _one(
            expansion(bbw_rank(b.close, 20, 2.0, 126), bandwidth(b.close, 20, 2.0), 85.0, 3)
        ),
        "volume_oscillator": lambda b: _one(volume_oscillator(b.volume, 5, 10)),
        "relative_volume": lambda b: _one(relative_volume(b.volume, 20)),
        "obv_slope_sign": lambda b: _one(obv_slope_sign(b.close, b.volume, 20)),
        "cmf": lambda b: _one(cmf(b.high, b.low, b.close, b.volume, 20)),
        "accumulation_distribution_days": lambda b: _arrays(
            accumulation_distribution_days(b.close, b.volume)
        ),
        "divergence_series": _div_series,
        "split_volume": lambda b: dict(
            zip(
                ("buy", "sell"),
                split_volume(b.high, b.low, b.close, b.volume, _prev_close(b)),
                strict=True,
            )
        ),
    }
    lags = {"divergence_series": 0}
    asof: dict[str, AsofAdapter] = {
        "pivots": lambda b, t: [
            p for p in pivots(b.high, b.low, PIVOT_WIDTH) if p.confirmed_at <= t
        ],
        "pivot_confirmation_bar": lambda b, t: pivot_confirmation_bar(t, PIVOT_WIDTH),
        "zigzag": _zigzag_asof,
        "resample_weekly": _resample_asof,
        "last_cross": lambda b, t: last_cross(
            sma(b.close[: t + 1], 20), sma(b.close[: t + 1], 50), 3
        ),
        "macd_signal_cross": lambda b, t: macd_signal_cross(
            macd(b.close[: t + 1]).line, macd(b.close[: t + 1]).signal, 3
        ),
        "fib_leg": lambda b, t: fib_leg(b.high[: t + 1], b.low[: t + 1], b.close[: t + 1]),
        "near": _near_asof,
        "holding": _holding_asof,
        "recency_weight": lambda b, t: recency_weight(min(t, 300)),
        "support_resistance": lambda b, t: support_resistance(
            b.high[: t + 1], b.low[: t + 1], b.close[: t + 1], b.volume[: t + 1]
        ),
        "detect_divergences": lambda b, t: detect_divergences(
            b.high, b.low, rsi(b.close, 14), oscillator="rsi", as_of=t
        ),
        "detect_all_divergences": lambda b, t: detect_all_divergences(
            b.high, b.low, b.close, b.volume, as_of=t
        ),
        "divergence_records": lambda b, t: [
            r
            for r in divergence_records(b.high, b.low, rsi(b.close, 14), oscillator="rsi")
            if r.confirmed_at <= t
        ],
        "detect_weekly_divergences": _weekly_div_asof,
    }
    both = {"estimate_order_flow": (_flow_series, _flow_asof)}
    lags |= {"pivot_masks": PIVOT_WIDTH}
    series["pivot_masks"] = lambda b: {
        k: m.astype(np.float64)
        for k, m in zip(("high", "low"), pivot_masks(b.high, b.low, PIVOT_WIDTH), strict=True)
    }
    out = [Entry(n, series=f, confirm_lag=lags.get(n, 0)) for n, f in series.items()]
    out += [Entry(n, asof=f) for n, f in asof.items()]
    out += [Entry(n, series=s, asof=a) for n, (s, a) in both.items()]
    return sorted(out, key=lambda e: e.name)


REGISTRY: dict[str, Entry] = {e.name: e for e in _entries()}

EXEMPT: dict[str, str] = {
    "AccDistDays": "record returned by accumulation_distribution_days",
    "Adx": "record returned by adx",
    "Bollinger": "record returned by bollinger",
    "Cross": "record returned by last_cross and macd_signal_cross",
    "Divergence": "record returned by the divergence detectors",
    "DivergenceSeries": "record returned by divergence_series",
    "EXTENSION_RATIOS": "constant tuple of Fibonacci extension ratios",
    "FibLeg": "record returned by fib_leg",
    "FlowQuality": "enum describing the data path of estimate_order_flow",
    "FlowResult": "record returned by estimate_order_flow",
    "Level": "record inside SupportResistance",
    "Macd": "record returned by macd and macd_weekly",
    "Pivot": "record returned by pivots",
    "RETRACEMENT_RATIOS": "constant tuple of Fibonacci retracement ratios",
    "SmaStack": "record returned by sma_stack",
    "SupertrendResult": "record returned by supertrend",
    "SupportResistance": "record returned by support_resistance",
    "Swing": "record inside ZigZag",
    "TradesClassifier": "protocol for a plug-in tick classifier, not an indicator",
    "WeeklyBars": "record returned by resample_weekly",
    "ZigZag": "record returned by zigzag",
}


def unregistered(
    names: list[str] | None = None, registry: dict[str, Entry] | None = None
) -> list[str]:
    """Names in `indicators.__all__` (or `names`) that are neither registered nor exempt."""
    if names is None:
        import supertrends.indicators as package  # noqa: PLC0415 - registry is a leaf module

        names = list(package.__all__)
    known = set(REGISTRY if registry is None else registry) | set(EXEMPT)
    return sorted(n for n in names if n not in known)


def compute_all(bundle: Bundle, registry: dict[str, Entry] | None = None) -> dict[str, object]:
    """Canonical output of every registered indicator on `bundle`, as of its last bar."""
    last = len(bundle) - 1
    out: dict[str, object] = {}
    for name, entry in (REGISTRY if registry is None else registry).items():
        part: dict[str, object] = {}
        if entry.series is not None:
            part["series"] = canonical(entry.series(bundle))
        if entry.asof is not None:
            part["asof"] = canonical(entry.asof(bundle, last))
        out[name] = part
    return out
