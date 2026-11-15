# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Watchlist service, seed loader, and ingestion set (PRD FR-001..FR-012, ARCHITECTURE 5.1, 6.1).

One default watchlist holds items (one row per symbol) and named groups; membership is
many-to-many (ADR-019). The functions here are dialect-neutral and never commit: the caller
owns the transaction. Symbol validation goes through a `SymbolResolver`, the narrow slice of
`MarketDataProvider.resolve_symbol` (ARCHITECTURE 7.2) the watchlist needs.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supertrends.data.models import (
    WATCHLIST_ITEM_CAP,
    Ticker,
    Watchlist,
    WatchlistGroup,
    WatchlistGroupMember,
    WatchlistItem,
)
from supertrends.errors import ConfigError, SuperTrendsError

SYMBOL_PATTERN = r"^[A-Z][A-Z0-9.\-]{0,9}$"
SYMBOL_RE = re.compile(SYMBOL_PATTERN)
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
GROUP_NAME_MAX = 64
DEFAULT_WATCHLIST_NAME = "default"
DEFAULT_BENCHMARKS = ("SPY", "QQQ")
DEFAULT_SEED_PATH = "config/watchlist.seed.yaml"
# A needs_review note containing one of these is attempted against provider reference data
# (and falls back to `unresolved`); any other note starts the symbol excluded (PRD FR-008).
ATTEMPT_MARKERS = ("may be missing", "current symbol", "still listed", "market-regime input")
INDEX_ONLY_SYMBOLS = ("VIX",)  # stored, ingested if offered, never scored (FR-009)


class WatchlistError(SuperTrendsError):
    """A watchlist rule was violated; carries the HTTP status and problem slug (ARCH 6.0)."""

    status = 422
    slug = "validation-error"
    title = "Invalid request"

    def __init__(self, detail: str, errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.errors = errors


class AlreadyExistsError(WatchlistError):
    """The symbol or group slug already exists."""

    status = 409
    slug = "already-exists"
    title = "Already exists"


class NotFoundError(WatchlistError):
    """The watchlist, item, or group does not exist."""

    status = 404
    slug = "not-found"
    title = "Not found"


class WatchlistFullError(WatchlistError):
    """The watchlist already holds the maximum number of items."""

    status = 422
    slug = "watchlist-full"
    title = "Watchlist is full"


class SymbolUnresolvedError(WatchlistError):
    """Provider reference data cannot resolve the symbol."""

    status = 422
    slug = "symbol-unresolved"
    title = "Symbol could not be resolved"


class ResolvedSymbol(Protocol):
    """The reference data the watchlist reads (matches providers.base.SymbolInfo)."""

    @property
    def name(self) -> str | None:
        """Display name."""
        ...

    @property
    def type(self) -> str:
        """One of stock, etf, index, crypto."""
        ...

    @property
    def active(self) -> bool:
        """Whether the symbol is currently listed."""
        ...


class SymbolResolver(Protocol):
    """Resolves a symbol against provider reference data; None when it is unknown."""

    def resolve_symbol(self, symbol: str) -> ResolvedSymbol | None:
        """Return reference data for `symbol`, or None."""
        ...


@dataclass(frozen=True)
class PermissiveSymbol:
    """Reference data of the permissive resolver."""

    name: str | None = None
    type: str = "stock"
    active: bool = True


class PermissiveResolver:
    """Accepts every regex-valid symbol (fixture provider permissive mode, tests)."""

    def resolve_symbol(self, symbol: str) -> ResolvedSymbol | None:
        """Resolve any symbol that matches the symbol regex."""
        return PermissiveSymbol() if SYMBOL_RE.fullmatch(symbol) else None


@dataclass(frozen=True)
class ItemView:
    """One watchlist item as exposed by the API."""

    symbol: str
    name: str | None
    type: str
    scored: bool
    resolution: str
    resolution_reason: str | None
    added_at: dt.datetime
    groups: list[str]


@dataclass(frozen=True)
class GroupView:
    """One watchlist group as exposed by the API."""

    slug: str
    name: str
    position: int
    symbols: list[str]


@dataclass(frozen=True)
class WatchlistView:
    """The default watchlist with items and groups."""

    id: int
    name: str
    count: int
    max: int
    groups: list[GroupView]
    items: list[ItemView]
    benchmarks: list[str]


@dataclass
class SeedResult:
    """What a seed load did."""

    groups: int = 0
    symbols: int = 0
    resolved: list[str] = field(default_factory=list)
    unresolved: dict[str, str] = field(default_factory=dict)
    needs_review: dict[str, str] = field(default_factory=dict)
    rejected: dict[str, str] = field(default_factory=dict)  # cannot be stored (symbol format)


class SeedGroup(BaseModel):
    """One group in the seed file."""

    model_config = ConfigDict(extra="forbid")

    tradingview_name: str = Field(max_length=GROUP_NAME_MAX)
    source: str
    symbols: list[str]


class WatchlistSeed(BaseModel):
    """The validated `config/watchlist.seed.yaml` document."""

    model_config = ConfigDict(extra="forbid")

    version: int
    benchmarks: list[str]
    groups: dict[str, SeedGroup]
    needs_review: dict[str, str] = Field(default_factory=dict)

    def unique_symbols(self) -> list[str]:
        """Every distinct symbol, in first-seen order."""
        seen: dict[str, None] = {}
        for group in self.groups.values():
            seen.update(dict.fromkeys(group.symbols))
        return list(seen)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def seed_path() -> Path:
    """Locate the seed file (working directory first, then the repository)."""
    for base in (Path.cwd(), Path(__file__).resolve().parents[3]):
        candidate = base / DEFAULT_SEED_PATH
        if candidate.is_file():
            return candidate
    msg = f"{DEFAULT_SEED_PATH} not found"
    raise ConfigError(msg)


def load_seed(path: Path | None = None) -> WatchlistSeed:
    """Read and validate the seed file."""
    target = path or seed_path()
    try:
        document = yaml.safe_load(target.read_text(encoding="utf-8"))
        return WatchlistSeed.model_validate(document)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        msg = f"invalid watchlist seed {target}: {exc}"
        raise ConfigError(msg) from exc


def normalize_symbol(symbol: str) -> str:
    """Uppercase and validate a symbol (ARCHITECTURE 6.0)."""
    value = symbol.strip().upper()
    if not SYMBOL_RE.fullmatch(value):
        msg = f"symbol must match {SYMBOL_PATTERN}"
        raise WatchlistError(msg, [{"loc": ["symbol"], "msg": msg}])
    return value


def get_default_watchlist(session: Session) -> Watchlist:
    """The default watchlist, or NotFoundError before the seed has run."""
    found = session.scalars(select(Watchlist).where(Watchlist.is_default.is_(True))).first()
    if found is None:
        msg = "default watchlist does not exist; run `supertrends watchlist seed`"
        raise NotFoundError(msg)
    return found


def _memberships(session: Session, watchlist_id: int) -> dict[str, list[str]]:
    rows = session.execute(
        select(WatchlistGroupMember.symbol, WatchlistGroup.slug)
        .join(WatchlistGroup, WatchlistGroup.id == WatchlistGroupMember.group_id)
        .where(WatchlistGroupMember.watchlist_id == watchlist_id)
        .order_by(WatchlistGroup.position, WatchlistGroup.slug)
    )
    result: dict[str, list[str]] = {}
    for symbol, slug in rows:
        result.setdefault(symbol, []).append(slug)
    return result


def _item_view(item: WatchlistItem, ticker: Ticker, groups: list[str]) -> ItemView:
    return ItemView(
        symbol=item.symbol,
        name=ticker.name,
        type=ticker.type,
        scored=item.scored and ticker.resolution == "resolved",
        resolution=ticker.resolution,
        resolution_reason=ticker.resolution_reason,
        added_at=item.added_at,
        groups=groups,
    )


def read_watchlist(session: Session) -> WatchlistView:
    """The default watchlist: items, groups, and benchmarks."""
    watchlist = get_default_watchlist(session)
    memberships = _memberships(session, watchlist.id)
    rows = session.execute(
        select(WatchlistItem, Ticker)
        .join(Ticker, Ticker.symbol == WatchlistItem.symbol)
        .where(WatchlistItem.watchlist_id == watchlist.id)
        .order_by(WatchlistItem.symbol)
    ).all()
    items = [_item_view(i, t, memberships.get(i.symbol, [])) for i, t in rows]
    by_group: dict[str, list[str]] = {}
    for item in items:
        for slug in item.groups:
            by_group.setdefault(slug, []).append(item.symbol)
    groups = [
        GroupView(g.slug, g.name, g.position, by_group.get(g.slug, []))
        for g in session.scalars(
            select(WatchlistGroup)
            .where(WatchlistGroup.watchlist_id == watchlist.id)
            .order_by(WatchlistGroup.position, WatchlistGroup.slug)
        )
    ]
    return WatchlistView(
        id=watchlist.id,
        name=watchlist.name,
        count=len(items),
        max=WATCHLIST_ITEM_CAP,
        groups=groups,
        items=items,
        benchmarks=list(DEFAULT_BENCHMARKS),
    )


def _groups_by_slug(
    session: Session, watchlist_id: int, slugs: Sequence[str]
) -> dict[str, WatchlistGroup]:
    wanted = list(dict.fromkeys(slugs))
    found = {
        g.slug: g
        for g in session.scalars(
            select(WatchlistGroup).where(
                WatchlistGroup.watchlist_id == watchlist_id, WatchlistGroup.slug.in_(wanted)
            )
        )
    }
    missing = [s for s in wanted if s not in found]
    if missing:
        raise WatchlistError(
            f"unknown group slug: {', '.join(missing)}",
            [{"loc": ["body", "groups"], "msg": f"unknown group slug: {s}"} for s in missing],
        )
    return {s: found[s] for s in wanted}


def _item_count(session: Session, watchlist_id: int) -> int:
    count = session.scalar(
        select(func.count())
        .select_from(WatchlistItem)
        .where(WatchlistItem.watchlist_id == watchlist_id)
    )
    return count or 0


def _view_of(session: Session, watchlist_id: int, symbol: str) -> ItemView:
    item = session.get(WatchlistItem, (watchlist_id, symbol))
    ticker = session.get(Ticker, symbol)
    if item is None or ticker is None:
        msg = f"{symbol} is not on the watchlist"
        raise NotFoundError(msg)
    return _item_view(item, ticker, _memberships(session, watchlist_id).get(symbol, []))


def _link(
    session: Session, watchlist_id: int, symbol: str, groups: dict[str, WatchlistGroup]
) -> None:
    for group in groups.values():
        session.add(
            WatchlistGroupMember(group_id=group.id, watchlist_id=watchlist_id, symbol=symbol)
        )
    session.flush()


def _unlink(session: Session, watchlist_id: int, symbol: str) -> None:
    session.execute(
        delete(WatchlistGroupMember).where(
            WatchlistGroupMember.watchlist_id == watchlist_id,
            WatchlistGroupMember.symbol == symbol,
        )
    )


def add_item(
    session: Session,
    symbol: str,
    groups: Sequence[str],
    resolver: SymbolResolver,
    *,
    source: str = "api",
) -> ItemView:
    """Validate, resolve, and add `symbol`; raises a WatchlistError subclass on any rule."""
    value = normalize_symbol(symbol)
    watchlist = get_default_watchlist(session)
    if session.get(WatchlistItem, (watchlist.id, value)) is not None:
        msg = f"{value} is already on the watchlist"
        raise AlreadyExistsError(msg)
    by_slug = _groups_by_slug(session, watchlist.id, groups)
    if _item_count(session, watchlist.id) >= WATCHLIST_ITEM_CAP:
        msg = f"the watchlist is full (maximum {WATCHLIST_ITEM_CAP} tickers)"
        raise WatchlistFullError(msg)
    info = resolver.resolve_symbol(value)
    if info is None or not info.active:
        msg = f"{value} was not found in the market data provider's reference data"
        raise SymbolUnresolvedError(msg)
    if info.type == "crypto":
        msg = f"{value} is a crypto symbol; crypto is not supported in v1"
        raise SymbolUnresolvedError(msg)
    ticker = session.get(Ticker, value)
    if ticker is None:
        ticker = Ticker(symbol=value, created_at=_now())
        session.add(ticker)
    ticker.name = info.name or ticker.name
    ticker.type = info.type
    ticker.active = True
    ticker.resolution = "resolved"
    ticker.resolution_reason = None
    ticker.updated_at = _now()
    session.flush()
    session.add(
        WatchlistItem(
            watchlist_id=watchlist.id,
            symbol=value,
            added_at=_now(),
            source=source,
            scored=info.type != "index",
        )
    )
    try:
        session.flush()
    except IntegrityError as exc:  # concurrent add of the same symbol
        msg = f"{value} is already on the watchlist"
        raise AlreadyExistsError(msg) from exc
    _link(session, watchlist.id, value, by_slug)
    return _view_of(session, watchlist.id, value)


def remove_item(session: Session, symbol: str) -> None:
    """Remove an item and its memberships; the ticker row and its history are kept."""
    value = normalize_symbol(symbol)
    watchlist = get_default_watchlist(session)
    if session.get(WatchlistItem, (watchlist.id, value)) is None:
        msg = f"{value} is not on the watchlist"
        raise NotFoundError(msg)
    _unlink(session, watchlist.id, value)
    session.execute(
        delete(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist.id, WatchlistItem.symbol == value
        )
    )
    session.flush()


def set_item_groups(session: Session, symbol: str, groups: Sequence[str]) -> ItemView:
    """Replace an item's group memberships (an empty list clears them)."""
    value = normalize_symbol(symbol)
    watchlist = get_default_watchlist(session)
    if session.get(WatchlistItem, (watchlist.id, value)) is None:
        msg = f"{value} is not on the watchlist"
        raise NotFoundError(msg)
    by_slug = _groups_by_slug(session, watchlist.id, groups)
    _unlink(session, watchlist.id, value)
    _link(session, watchlist.id, value, by_slug)
    return _view_of(session, watchlist.id, value)


def create_group(session: Session, slug: str, name: str, position: int = 0) -> GroupView:
    """Create a named group."""
    errors: list[dict[str, Any]] = []
    if not SLUG_RE.fullmatch(slug):
        errors.append({"loc": ["body", "slug"], "msg": "slug must match ^[a-z0-9][a-z0-9-]{0,47}$"})
    if not 1 <= len(name) <= GROUP_NAME_MAX:
        errors.append({"loc": ["body", "name"], "msg": f"name must be 1..{GROUP_NAME_MAX} chars"})
    if errors:
        raise WatchlistError("invalid group", errors)
    watchlist = get_default_watchlist(session)
    exists = session.scalars(
        select(WatchlistGroup.id).where(
            WatchlistGroup.watchlist_id == watchlist.id, WatchlistGroup.slug == slug
        )
    ).first()
    if exists is not None:
        msg = f"group {slug} already exists"
        raise AlreadyExistsError(msg)
    session.add(WatchlistGroup(watchlist_id=watchlist.id, slug=slug, name=name, position=position))
    session.flush()
    return GroupView(slug, name, position, [])


def delete_group(session: Session, slug: str) -> None:
    """Delete a group and its memberships, never its items."""
    watchlist = get_default_watchlist(session)
    group = session.scalars(
        select(WatchlistGroup).where(
            WatchlistGroup.watchlist_id == watchlist.id, WatchlistGroup.slug == slug
        )
    ).first()
    if group is None:
        msg = f"group {slug} does not exist"
        raise NotFoundError(msg)
    session.execute(delete(WatchlistGroupMember).where(WatchlistGroupMember.group_id == group.id))
    session.execute(delete(WatchlistGroup).where(WatchlistGroup.id == group.id))
    session.flush()


def _is_attempted(note: str) -> bool:
    lowered = note.lower()
    return any(marker in lowered for marker in ATTEMPT_MARKERS)


def _upsert_ticker(session: Session, symbol: str) -> Ticker:
    ticker = session.get(Ticker, symbol)
    if ticker is None:
        ticker = Ticker(symbol=symbol, created_at=_now(), updated_at=_now())
        session.add(ticker)
    return ticker


def seed_default_watchlist(
    session: Session,
    resolver: SymbolResolver | None = None,
    seed: WatchlistSeed | None = None,
) -> SeedResult | None:
    """Create the default watchlist from the seed, only if it does not exist yet.

    Returns None when the default watchlist already exists (later starts never reseed and
    owner edits are never undone). Otherwise every group and symbol is stored once with
    many-to-many membership. Without a `resolver` the seed symbols are stored unvalidated;
    with one, each is validated and an unresolvable symbol is recorded `unresolved` with a
    reason and excluded, never substituted. `needs_review` symbols start excluded unless
    their note says they should be attempted (PRD FR-008). Symbols that fail the symbol
    format cannot be stored and are reported in `rejected`.
    """
    existing = session.scalars(select(Watchlist.id).where(Watchlist.is_default.is_(True))).first()
    if existing is not None:
        return None
    document = seed or load_seed()
    result = SeedResult()
    watchlist = Watchlist(name=DEFAULT_WATCHLIST_NAME, is_default=True, created_at=_now())
    session.add(watchlist)
    session.flush()
    for symbol in document.benchmarks:
        bench = _upsert_ticker(session, symbol)
        bench.is_benchmark = True
        bench.type = "etf"
    stored: set[str] = set()
    for symbol in document.unique_symbols():
        if not SYMBOL_RE.fullmatch(symbol):
            result.rejected[symbol] = document.needs_review.get(
                symbol, "symbol does not match the required format"
            )
            continue
        _seed_symbol(session, watchlist.id, symbol, document, resolver, result)
        stored.add(symbol)
    session.flush()
    for position, (slug, group) in enumerate(document.groups.items()):
        row = WatchlistGroup(
            watchlist_id=watchlist.id, slug=slug, name=group.tradingview_name, position=position
        )
        session.add(row)
        session.flush()
        for symbol in dict.fromkeys(group.symbols):
            if symbol in stored:
                session.add(
                    WatchlistGroupMember(group_id=row.id, watchlist_id=watchlist.id, symbol=symbol)
                )
    result.groups = len(document.groups)
    result.symbols = len(stored)
    session.flush()
    return result


def _seed_symbol(  # noqa: PLR0913, PLR0917 (flat helper)
    session: Session,
    watchlist_id: int,
    symbol: str,
    document: WatchlistSeed,
    resolver: SymbolResolver | None,
    result: SeedResult,
) -> None:
    note = document.needs_review.get(symbol)
    ticker = _upsert_ticker(session, symbol)
    scored = symbol not in INDEX_ONLY_SYMBOLS
    if symbol in INDEX_ONLY_SYMBOLS:
        ticker.type = "index"
    if note is not None and not _is_attempted(note):
        ticker.resolution = "needs_review"
        ticker.resolution_reason = note
        result.needs_review[symbol] = note
        scored = False
    elif resolver is not None:
        info = resolver.resolve_symbol(symbol)
        if info is None or not info.active:
            reason = "not found in the market data provider's reference data"
            if note:
                reason = f"{reason} ({note})"
            ticker.resolution = "unresolved"
            ticker.resolution_reason = reason
            result.unresolved[symbol] = reason
            scored = False
        else:
            ticker.resolution = "resolved"
            ticker.name = info.name or ticker.name
            if symbol not in INDEX_ONLY_SYMBOLS:
                ticker.type = info.type
            result.resolved.append(symbol)
    else:
        result.resolved.append(symbol)
    session.add(
        WatchlistItem(
            watchlist_id=watchlist_id, symbol=symbol, added_at=_now(), source="seed", scored=scored
        )
    )


def seed_if_empty(resolver: SymbolResolver | None = None) -> SeedResult | None:
    """Seed the default watchlist in its own transaction (app start and `watchlist seed`)."""
    from supertrends.data.db import session_scope  # noqa: PLC0415 (keeps imports light)

    try:
        with session_scope() as session:
            return seed_default_watchlist(session, resolver)
    except IntegrityError:  # another replica seeded first
        return None


def symbols_to_ingest(session: Session) -> list[str]:
    """Symbols the daily ingest must fetch, sorted.

    Watchlist items that resolved and are active (scored or ingest-only such as VIX), plus
    the SPY and QQQ benchmarks even when removed from the watchlist. Crypto, `unresolved`,
    and `needs_review` symbols are excluded.
    """
    rows = session.scalars(
        select(WatchlistItem.symbol)
        .join(Ticker, Ticker.symbol == WatchlistItem.symbol)
        .join(Watchlist, Watchlist.id == WatchlistItem.watchlist_id)
        .where(
            Watchlist.is_default.is_(True),
            Ticker.resolution == "resolved",
            Ticker.active.is_(True),
            Ticker.type != "crypto",
        )
    )
    return sorted({*rows, *DEFAULT_BENCHMARKS})
