# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Read endpoints, run trigger and config under /api/v1 (ARCHITECTURE 6.1, FR-801 to 807, ADR-072).

Reads are open and never write; `POST /runs` needs the bearer token and only queues a run
(ADR-020). "Latest" means the current published run with the greatest trade date. Every payload
that carries a pick or score includes the disclaimer (FR-805). Unknown query parameters are
rejected with 422. LLM text only ever appears as stored narrative; it never feeds a number here.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping, Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.dependencies.models import Dependant
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from supertrends.api.deps import ClockDep, ScoringConfigDep, StoreDep
from supertrends.api.problems import ProblemError
from supertrends.api.schemas import read as m
from supertrends.api.security import require_write_token
from supertrends.api.store import ReadStore
from supertrends.runs import dates
from supertrends.runs.dates import TradeDateError
from supertrends.runs.narrator import DISCLAIMER
from supertrends.runs.service import RecommendationView, RunView
from supertrends.scoring.config import FACTOR_IDS, ScoringConfig, config_hash

SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
ULID_PATTERN = r"^[0-9A-HJKMNP-TV-Z]{26}$"
TOP_FACTORS = 3
BAR_WINDOW_DAYS = {"1d": 365, "1w": 1826, "5m": 5}
BAR_MAX_SPAN_DAYS = {"1d": 3660, "1w": 3660, "5m": 30}
MARKET_CLOSED = "market_closed"
_DATE_PROBLEMS = {
    dates.NOT_A_TRADING_DATE: (422, "not-a-trading-date"),
    dates.DATE_IN_FUTURE: (422, "date-in-future"),
    dates.SESSION_NOT_COMPLETE: (409, "session-not-complete"),
}


def _query_names(dependant: Dependant) -> set[str]:
    names = {p.alias for p in dependant.query_params}
    for sub in dependant.dependencies:
        names |= _query_names(sub)
    return names


def reject_unknown_query(request: Request) -> None:
    """Fail with 422 when the request carries a query parameter the route does not declare."""
    route = request.scope["route"]
    allowed = _query_names(route.dependant)
    unknown = sorted(set(request.query_params) - allowed)
    if unknown:
        raise RequestValidationError(
            [
                {"type": "extra_forbidden", "loc": ("query", k), "msg": "Unknown query parameter"}
                for k in unknown
            ]
        )


router = APIRouter(dependencies=[Depends(reject_unknown_query)])
Cursor = Annotated[str | None, Query(pattern=ULID_PATTERN)]


def _invalid(where: str, name: str, msg: str) -> RequestValidationError:
    return RequestValidationError([{"type": "value_error", "loc": (where, name), "msg": msg}])


def _trade_date_problem(exc: TradeDateError) -> ProblemError:
    status, slug = _DATE_PROBLEMS.get(exc.code, (422, "validation-error"))
    detail = str(exc)
    if exc.code == dates.NOT_A_TRADING_DATE:
        detail = detail.replace("is not an XNYS session", "is not a trading date (XNYS session)")
    return ProblemError(status, slug, detail)


def _published_run(store: ReadStore, requested: dt.date | None, now: dt.datetime) -> RunView:
    """The current published run for `requested`, or the latest."""
    if requested is None:
        run = store.latest_published()
        if run is None:
            raise ProblemError(404, "no-published-run", "There is no published run yet.")
        return run
    try:
        dates.resolve_trade_date(requested, now)
    except TradeDateError as exc:
        raise _trade_date_problem(exc) from None
    run = store.published_for_date(requested)
    if run is None:
        msg = f"There is no published run for {requested.isoformat()}."
        raise ProblemError(404, "no-published-run", msg)
    return run


def _config_ref(run: RunView, cfg: ScoringConfig) -> m.ConfigRef:
    active = config_hash(cfg) == run.config_hash
    return m.ConfigRef(version=cfg.scoring.version if active else None, hash=run.config_hash)


def _excluded(summary: Mapping[str, Any]) -> list[m.Excluded]:
    return [m.Excluded(ticker=e["ticker"], reason=e["reason"]) for e in summary.get("excluded", [])]


def _confidence(value: float) -> int:
    return round(value)


def _pick(
    rec: RecommendationView, expected_move: float | None, ribbon: str, doc: Mapping[str, Any]
) -> m.Pick:
    ev = rec.evidence
    st = ev.get("supertrend") or {}
    inv = ev.get("invalidation") or {}
    factors = sorted(ev.get("factors") or [], key=lambda f: -abs(float(f["contribution"])))
    narrative = rec.narrative
    return m.Pick(
        recommendation_id=rec.id,
        side=rec.side,
        rank=rec.rank,
        ticker=rec.symbol,
        display_score=rec.display_score,
        band=rec.band,
        confidence=_confidence(rec.confidence),
        regime=ev.get("regime"),
        supertrend=m.SupertrendBlock(
            dir_d=st.get("dir_d"),
            dir_w=st.get("dir_w"),
            bars_since_flip=st.get("bars_since_flip"),
            line=st.get("line"),
        ),
        invalidation=m.Invalidation(level=inv.get("level"), rule=inv.get("rule")),
        top_factors=[
            m.TopFactor(id=f["id"], contribution=f["contribution"]) for f in factors[:TOP_FACTORS]
        ],
        ribbon=ribbon,
        flags=[str(f) for f in ev.get("flags") or []],
        days_on_list=ev.get("days_on_list"),
        expected_1d_move=expected_move,
        levels=ev.get("levels"),
        narrative=None
        if narrative is None
        else m.NarrativeOut(text=narrative.text, source=narrative.source, model=narrative.model),
        entry_price=rec.entry_price,
        entry_date=rec.entry_date,
    )


def _nearest(raw: Mapping[str, Any] | None) -> m.NearestMiss | None:
    if not raw:
        return None
    return m.NearestMiss(
        ticker=raw["ticker"], display_score=raw["display_score"], reason=raw["reason"]
    )


def _recommendations(
    store: ReadStore, run: RunView, cfg: ScoringConfig
) -> m.RecommendationsResponse:
    summary = run.summary
    picks = store.picks(run.id)
    also = list(summary.get("also_qualified") or [])
    extras = store.pick_extras(run.id, [p.symbol for p in picks], [a["ticker"] for a in also])
    cards = {
        side: [
            _pick(p, extras.expected_move.get(p.symbol), extras.ribbon.get(p.symbol, ""), summary)
            for p in picks
            if p.side == side
        ]
        for side in ("buy", "sell")
    }
    miss = summary.get("nearest_miss") or {}
    return m.RecommendationsResponse(
        date=run.trade_date,
        run_id=run.id,
        published_at=run.published_at,
        market_regime=run.market_regime,
        config=_config_ref(run, cfg),
        buys=cards["buy"],
        sells=cards["sell"],
        also_qualified=[
            m.AlsoQualified(
                ticker=a["ticker"],
                side=a["side"],
                display_score=extras.scores[a["ticker"]][0]
                if a["ticker"] in extras.scores
                else None,
                confidence=_confidence(extras.scores[a["ticker"]][1])
                if a["ticker"] in extras.scores
                else None,
                duplicates=a.get("duplicates"),
                correlation=a.get("correlation"),
            )
            for a in also
        ],
        nearest_miss=m.NearestMisses(
            buy=_nearest(miss.get("buy")), sell=_nearest(miss.get("sell"))
        ),
        excluded=_excluded(summary),
        summary=m.SummaryCounts(
            tickers_total=summary.get("tickers_total", 0),
            tickers_scored=summary.get("tickers_scored", 0),
            tickers_excluded=summary.get("tickers_excluded", 0),
            narrative_llm=summary.get("narrative_llm", 0),
            narrative_template=summary.get("narrative_template", 0),
            duration_seconds=summary.get("duration_seconds"),
        ),
        superseded_runs=[
            m.SupersededOut(id=s.id, published_at=s.published_at)
            for s in store.superseded_for_date(run.trade_date)
        ],
        disclaimer=DISCLAIMER,
    )


@router.get(
    "/recommendations/latest",
    response_model=m.RecommendationsResponse,
    summary="Picks of the latest published run",
)
def recommendations_latest(store: StoreDep, cfg: ScoringConfigDep) -> m.RecommendationsResponse:
    """Buys, sells, also-qualified, nearest miss and exclusions of the latest published run."""
    run = store.latest_published()
    if run is None:
        raise ProblemError(404, "no-published-run", "There is no published run yet.")
    return _recommendations(store, run, cfg)


@router.get(
    "/recommendations",
    response_model=m.RecommendationsResponse,
    summary="Picks of a trade date",
)
def recommendations_by_date(
    date: Annotated[dt.date, Query(description="Trade date (an XNYS session).")],
    store: StoreDep,
    cfg: ScoringConfigDep,
    now: ClockDep,
) -> m.RecommendationsResponse:
    """The current published run of `date`."""
    return _recommendations(store, _published_run(store, date, now), cfg)


@router.get("/rankings", response_model=m.RankingsResponse, summary="Ranking of a run")
def rankings(  # noqa: PLR0913, PLR0917 (FastAPI parameters)
    store: StoreDep,
    now: ClockDep,
    date: dt.date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
    group: Annotated[str | None, Query(pattern=r"^[a-z0-9][a-z0-9-]{0,47}$")] = None,
) -> m.RankingsResponse:
    """Scored tickers by rank, optionally limited to a watchlist group."""
    run = _published_run(store, date, now)
    page = store.rankings(run.id, limit, offset, group)
    if page is None:
        raise ProblemError(404, "not-found", f"Unknown group: {group}.")
    picks = {p.symbol: p.side for p in store.picks(run.id)}
    for a in run.summary.get("also_qualified") or []:
        picks.setdefault(a["ticker"], "also_qualified")
    return m.RankingsResponse(
        date=run.trade_date,
        run_id=run.id,
        total=page.total,
        limit=limit,
        offset=offset,
        items=[
            m.RankingItem(
                rank=r.rank,
                ticker=r.ticker,
                display_score=r.display_score,
                band=r.band,
                confidence=_confidence(r.confidence),
                composite=r.composite,
                regime=r.regime,
                st_dir_d=r.st_dir_d,
                st_dir_w=r.st_dir_w,
                bars_since_flip=r.bars_since_flip,
                candidate=r.candidate,
                flags=r.flags,
                groups=r.groups,
                picked=picks.get(r.ticker),
            )
            for r in page.rows
        ],
        excluded=_excluded(run.summary),
        disclaimer=DISCLAIMER,
    )


def _symbol(raw: str) -> str:
    symbol = raw.upper()
    if not SYMBOL_RE.match(symbol):
        raise _invalid("path", "symbol", "Not a valid ticker symbol")
    return symbol


def _factor_outs(rows: Sequence[Any], weights: Mapping[str, Any] | None) -> list[m.FactorOut]:
    by_id = {f.id: f for f in rows}
    out: list[m.FactorOut] = []
    for fid in FACTOR_IDS:
        f = by_id.get(fid)
        if f is None:
            continue
        w = (weights or {}).get(fid) or {}
        out.append(
            m.FactorOut(
                id=fid,
                score=f.score,
                base_weight=w.get("base"),
                weight=w.get("final", f.weight),
                contribution=f.contribution,
                quality=f.quality,
                reasons=[str(i["reason"]) for i in f.items if i.get("reason")],
            )
        )
    return out


@router.get(
    "/tickers/{symbol}/analysis",
    response_model=m.AnalysisResponse,
    summary="Factor breakdown of a ticker",
)
def ticker_analysis(
    symbol: Annotated[str, Path()],
    store: StoreDep,
    cfg: ScoringConfigDep,
    now: ClockDep,
    date: dt.date | None = None,
) -> m.AnalysisResponse:
    """Every factor's score, weight and reasons, or why the ticker was excluded."""
    sym = _symbol(symbol)
    run = _published_run(store, date, now)
    info = store.ticker(sym)
    if info is None:
        raise ProblemError(404, "ticker-not-found", f"Unknown ticker: {sym}.")
    rows = store.analysis_rows(run.id, sym)
    pick = next((p for p in store.picks(run.id) if p.symbol == sym), None)
    base: dict[str, Any] = {
        "ticker": sym,
        "name": info.name,
        "date": run.trade_date,
        "run_id": run.id,
        "market_regime": run.market_regime,
        "config": _config_ref(run, cfg),
        "disclaimer": DISCLAIMER,
    }
    if rows is None:
        return m.AnalysisResponse(
            **base,
            status="excluded",
            exclusion_reason="not_in_run",
            data_quality=None,
            display_score=None,
            band=None,
            confidence=None,
            composite=None,
            regime=None,
            candidate=None,
            thresholds=m.Thresholds(buy=None, sell=None),
            factors=[],
            adjustments=[],
            flags=[],
            supertrend=m.SupertrendBlock(),
            ripster=m.RipsterBlock(),
            expected_1d_move=None,
            picked=None,
            narrative=None,
        )
    s = rows.score
    snap = rows.snapshot or {}
    daily = snap.get("daily") or {}
    atr = daily.get("atr")
    narrative = None if pick is None or pick.narrative is None else pick.narrative
    return m.AnalysisResponse(
        **base,
        status=s.status,
        exclusion_reason=s.exclusion_reason,
        data_quality=s.data_quality,
        display_score=s.display_score,
        band=s.band,
        confidence=None if s.confidence is None else _confidence(s.confidence),
        composite=s.composite,
        regime=s.regime,
        candidate=s.candidate,
        thresholds=m.Thresholds(buy=s.buy_threshold, sell=s.sell_threshold),
        factors=_factor_outs(rows.factors, s.weights),
        adjustments=s.adjustments,
        flags=s.flags,
        supertrend=m.SupertrendBlock(
            dir_d=s.st_dir_d,
            dir_w=s.st_dir_w,
            bars_since_flip=s.bars_since_flip,
            line=s.st_line,
            distance_atr=daily.get("distance_atr"),
        ),
        ripster=m.RipsterBlock(
            **{
                k: v
                for k, v in (snap.get("ripster") or {}).items()
                if k in m.RipsterBlock.model_fields
            }
        ),
        expected_1d_move=None if atr is None else round(float(atr), 2),
        picked=None
        if pick is None
        else m.PickedRef(side=pick.side, rank=pick.rank, recommendation_id=pick.id),
        narrative=None
        if narrative is None
        else m.NarrativeOut(text=narrative.text, source=narrative.source, model=narrative.model),
    )


def _bar_time(value: dt.date | dt.datetime) -> str:
    if isinstance(value, dt.datetime):
        return value.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return value.isoformat()


@router.get(
    "/tickers/{symbol}/bars",
    response_model=m.BarsResponse,
    response_model_by_alias=True,
    summary="Bars and overlays of a ticker",
)
def ticker_bars(
    symbol: Annotated[str, Path()],
    store: StoreDep,
    tf: Annotated[str, Query(pattern="^(1d|1w|5m)$")] = "1d",
    from_: Annotated[dt.date | None, Query(alias="from")] = None,
    to: dt.date | None = None,
) -> m.BarsResponse:
    """OHLCV bars in `[from, to]` (default: the latest window) with chart overlays."""
    sym = _symbol(symbol)
    if store.ticker(sym) is None:
        raise ProblemError(404, "ticker-not-found", f"Unknown ticker: {sym}.")
    end = to or store.latest_bar_date(sym, tf)
    if end is None:
        return m.BarsResponse.model_validate(
            {"ticker": sym, "tf": tf, "from": None, "to": None, "bars": [], "overlays": {}}
        )
    start = from_ or end - dt.timedelta(days=BAR_WINDOW_DAYS[tf])
    if start > end:
        raise _invalid("query", "from", "`from` must not be after `to`")
    if (end - start).days > BAR_MAX_SPAN_DAYS[tf]:
        raise _invalid(
            "query", "from", f"The {tf} range is limited to {BAR_MAX_SPAN_DAYS[tf]} days"
        )
    data = store.bars(sym, tf, start, end)
    first = data.bars[0].t if data.bars else None
    last = data.bars[-1].t if data.bars else None
    return m.BarsResponse.model_validate(
        {
            "ticker": sym,
            "tf": tf,
            "from": None if first is None else _date_of(first),
            "to": None if last is None else _date_of(last),
            "bars": [
                {"t": _bar_time(b.t), "o": b.o, "h": b.h, "l": b.l, "c": b.c, "v": b.v}
                for b in data.bars
            ],
            "overlays": data.overlays,
        }
    )


def _date_of(value: dt.date | dt.datetime) -> dt.date:
    return value.astimezone(dt.UTC).date() if isinstance(value, dt.datetime) else value


def _run_list_item(run: RunView) -> m.RunListItem:
    s = run.summary
    return m.RunListItem(
        id=run.id,
        trade_date=run.trade_date,
        state=run.state,
        trigger=run.trigger,
        created_at=run.created_at,
        finished_at=run.finished_at,
        published_at=run.published_at,
        superseded_by=run.superseded_by,
        error_code=run.error_code,
        picks={"buy": len(s.get("buys") or []), "sell": len(s.get("sells") or [])},
        duration_seconds=s.get("duration_seconds"),
    )


@router.get("/runs", response_model=m.RunListResponse, summary="Runs, newest first")
def list_runs(
    store: StoreDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    before: Cursor = None,
) -> m.RunListResponse:
    """A page of runs; `next_before` is the cursor for the next page."""
    runs = store.list_runs(limit, before)
    return m.RunListResponse(
        items=[_run_list_item(r) for r in runs],
        next_before=runs[-1].id if len(runs) == limit else None,
    )


@router.get("/runs/{run_id}", response_model=m.RunDetail, summary="One run with its history")
def get_run(run_id: Annotated[str, Path(pattern=ULID_PATTERN)], store: StoreDep) -> m.RunDetail:
    """State, summary, exclusions and transitions of one run."""
    run = store.get_run(run_id)
    if run is None:
        raise ProblemError(404, "not-found", f"Unknown run: {run_id}.")
    s = run.summary
    return m.RunDetail(
        id=run.id,
        trade_date=run.trade_date,
        state=run.state,
        trigger=run.trigger,
        config_hash=run.config_hash,
        code_version=run.code_version,
        market_regime=run.market_regime,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        published_at=run.published_at,
        superseded_by=run.superseded_by,
        error_code=run.error_code,
        error_detail=run.error_detail,
        summary=m.RunSummaryOut(
            tickers_total=s.get("tickers_total"),
            tickers_scored=s.get("tickers_scored"),
            tickers_excluded=s.get("tickers_excluded"),
            excluded=_excluded(s),
            buys=list(s.get("buys") or []),
            sells=list(s.get("sells") or []),
            narrative=m.NarrativeCounts(
                llm=s.get("narrative_llm", 0), template=s.get("narrative_template", 0)
            ),
            duration_seconds=s.get("duration_seconds"),
        ),
        transitions=[
            m.TransitionOut.model_validate(
                {"seq": t.seq, "from": t.from_state, "to": t.to_state, "at": t.at}
            )
            for t in run.transitions
        ],
    )


@router.post(
    "/runs",
    status_code=202,
    response_model=m.RunTriggerResponse,
    dependencies=[Depends(require_write_token)],
    responses={200: {"model": m.MarketClosedResponse, "description": "No session to run."}},
    summary="Queue a run",
)
def trigger_run(
    response: Response,
    store: StoreDep,
    cfg: ScoringConfigDep,
    now: ClockDep,
    body: m.RunTriggerRequest | None = None,
) -> Any:
    """Queue a run for `date` (default: today's completed session). A worker executes it."""
    requested = body.date if body else None
    try:
        trade_date = dates.resolve_trade_date(requested, now)
    except TradeDateError as exc:
        code = getattr(exc, "code", "")
        if code == MARKET_CLOSED or (requested is None and code == dates.NOT_A_TRADING_DATE):
            return JSONResponse({"run_id": None, "state": MARKET_CLOSED}, status_code=200)
        raise _trade_date_problem(exc) from None
    result = store.trigger(cfg, trade_date)
    if result.status == "already_running":
        active = result.active_run_id
        detail = f"Run {active} is already in progress." if active else "A run is in progress."
        raise ProblemError(409, "run-in-progress", detail, extra={"active_run_id": active})
    run_id = result.run_id or ""
    response.headers["Location"] = f"/api/v1/runs/{run_id}"
    return m.RunTriggerResponse(run_id=run_id, state="queued", trade_date=trade_date)


@router.get("/config/scoring", response_model=m.ConfigResponse, summary="The active scoring config")
def scoring_config(request: Request, cfg: ScoringConfigDep, now: ClockDep) -> m.ConfigResponse:
    """The validated scoring config and its hash."""
    loaded = getattr(request.app.state, "config_loaded_at", None) or now
    return m.ConfigResponse(
        version=cfg.scoring.version,
        hash=config_hash(cfg),
        document=cfg.model_dump(mode="json"),
        loaded_at=loaded,
    )
