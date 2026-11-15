# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Watchlist service and seed (TS-WL; SQLite stand-in, no network)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from supertrends.data import watchlist as wl
from supertrends.data.models import (
    WATCHLIST_ITEM_CAP,
    Ticker,
    WatchlistGroupMember,
    WatchlistItem,
)
from supertrends.errors import ConfigError

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "config" / "watchlist.seed.yaml"
CRYPTO = REPO / "config" / "watchlist.crypto.yaml"
HARD_REVIEW = {"CITI", "XIC", "VCX", "CBRS"}


@dataclass(frozen=True)
class Info:
    name: str | None = "Name"
    type: str = "stock"
    active: bool = True


class Universe:
    """Resolver that knows a fixed set of symbols."""

    def __init__(self, unknown: set[str] | None = None, types: dict[str, str] | None = None):
        self.unknown = unknown or set()
        self.types = types or {}
        self.calls: list[str] = []

    def resolve_symbol(self, symbol: str) -> Info | None:
        self.calls.append(symbol)
        if symbol in self.unknown:
            return None
        return Info(type=self.types.get(symbol, "stock"))


def _seeded(session: Session, resolver: wl.SymbolResolver | None = None) -> wl.SeedResult:
    result = wl.seed_default_watchlist(session, resolver or wl.PermissiveResolver())
    assert result is not None
    session.commit()
    return result


def test_unit_watchlist_seed_load_14_groups_200_symbols_succeeds() -> None:
    seed = wl.load_seed(SEED)
    assert len(seed.groups) == 14
    assert len(seed.unique_symbols()) == 200
    assert seed.benchmarks == ["SPY", "QQQ"]


def test_unit_watchlist_seed_load_into_database_stores_every_group(
    watchlist_session: Session,
) -> None:
    result = _seeded(watchlist_session)
    view = wl.read_watchlist(watchlist_session)
    assert result.groups == len(view.groups) == 14
    # 000660 does not match the symbol format and cannot be stored (tickers CHECK).
    assert set(result.rejected) == {"000660"}
    assert view.count == result.symbols == 199
    assert wl.get_default_watchlist(watchlist_session).name == "default"


def test_unit_watchlist_seed_multi_group_symbol_stored_once_three_memberships(
    watchlist_session: Session,
) -> None:
    _seeded(watchlist_session)
    # TSLA is in adam-khoo-ai-robotics, whatsapp-group, fab-7, trump-stocks
    tickers = watchlist_session.scalar(
        select(func.count()).select_from(Ticker).where(Ticker.symbol == "NVDA")
    )
    items = watchlist_session.scalar(
        select(func.count()).select_from(WatchlistItem).where(WatchlistItem.symbol == "NVDA")
    )
    members = watchlist_session.scalar(
        select(func.count())
        .select_from(WatchlistGroupMember)
        .where(WatchlistGroupMember.symbol == "NVDA")
    )
    assert (tickers, items) == (1, 1)
    assert members is not None
    assert members >= 3
    view = wl.read_watchlist(watchlist_session)
    nvda = next(i for i in view.items if i.symbol == "NVDA")
    assert len(nvda.groups) == members


def test_unit_watchlist_seed_needs_review_symbol_flagged_not_scored(
    watchlist_session: Session,
) -> None:
    result = _seeded(watchlist_session)
    assert set(result.needs_review) >= HARD_REVIEW
    view = {i.symbol: i for i in wl.read_watchlist(watchlist_session).items}
    for symbol in HARD_REVIEW:
        assert view[symbol].resolution == "needs_review"
        assert view[symbol].scored is False
        assert view[symbol].resolution_reason
    assert "CITI" not in wl.symbols_to_ingest(watchlist_session)
    assert "CITI" in view  # listed, not replaced by C


def test_unit_watchlist_seed_vix_not_scored_crypto_not_ingested(
    watchlist_session: Session,
) -> None:
    _seeded(watchlist_session)
    vix = next(i for i in wl.read_watchlist(watchlist_session).items if i.symbol == "VIX")
    assert (vix.type, vix.scored) == ("index", False)
    assert "VIX" in wl.symbols_to_ingest(watchlist_session)
    crypto = yaml.safe_load(CRYPTO.read_text(encoding="utf-8"))
    assert crypto["status"].startswith("deferred")
    crypto_symbols = {s for g in crypto["groups"].values() for s in g["symbols"]}
    stored = {t for (t,) in watchlist_session.execute(select(Ticker.symbol))}
    assert not crypto_symbols & stored
    assert not crypto_symbols & set(wl.symbols_to_ingest(watchlist_session))


def test_unit_watchlist_seed_unresolvable_symbol_marked_unresolved_never_substituted(
    watchlist_session: Session,
) -> None:
    universe = Universe(unknown={"SQ", "XIACF", "SPLG"})
    result = _seeded(watchlist_session, universe)
    assert set(result.unresolved) == {"SQ", "XIACF", "SPLG"}
    view = {i.symbol: i for i in wl.read_watchlist(watchlist_session).items}
    assert view["SQ"].resolution == "unresolved"
    assert view["SQ"].resolution_reason
    assert view["SQ"].scored is False
    assert "XYZ" not in view  # SQ is never replaced by its renamed ticker
    ingest = wl.symbols_to_ingest(watchlist_session)
    assert not {"SQ", "XIACF", "SPLG"} & set(ingest)
    assert "KRKNF" in universe.calls  # attempted note symbols are validated
    assert "CITI" not in universe.calls  # hard needs_review symbols are not attempted


def test_unit_watchlist_seed_second_start_does_not_reseed_or_duplicate(
    watchlist_session: Session,
) -> None:
    _seeded(watchlist_session)
    wl.remove_item(watchlist_session, "NVDA")
    watchlist_session.commit()
    assert wl.seed_default_watchlist(watchlist_session, wl.PermissiveResolver()) is None
    view = wl.read_watchlist(watchlist_session)
    assert view.count == 198
    assert "NVDA" not in {i.symbol for i in view.items}


def test_unit_watchlist_seed_without_resolver_stores_symbols_unvalidated(
    watchlist_session: Session,
) -> None:
    result = wl.seed_default_watchlist(watchlist_session)
    assert result is not None
    assert not result.unresolved
    assert "SQ" in result.resolved


def test_unit_watchlist_seed_invalid_file_raises_config_error(tmp_path: Path) -> None:
    bad = tmp_path / "seed.yaml"
    bad.write_text("version: 1\nbogus: true\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        wl.load_seed(bad)
    with pytest.raises(ConfigError):
        wl.load_seed(tmp_path / "missing.yaml")


def test_unit_watchlist_seed_path_found_from_repository() -> None:
    assert wl.seed_path().name == "watchlist.seed.yaml"


def test_unit_watchlist_symbol_regex_rejects_lowercase_and_overlong_returns_422() -> None:
    assert wl.normalize_symbol(" brk.b ") == "BRK.B"
    for bad in ("", "1ABC", "ABCDEFGHIJK", "A B", "A$"):
        with pytest.raises(wl.WatchlistError) as caught:
            wl.normalize_symbol(bad)
        assert caught.value.status == 422


def test_unit_watchlist_validation_fixture_provider_permissive_regex_accepts_synthetic() -> None:
    resolver = wl.PermissiveResolver()
    assert resolver.resolve_symbol("ZZZZ") is not None
    assert resolver.resolve_symbol("zz") is None


def test_unit_watchlist_add_duplicate_symbol_returns_409_no_second_row(
    watchlist_session: Session,
) -> None:
    _seeded(watchlist_session)
    with pytest.raises(wl.AlreadyExistsError):
        wl.add_item(watchlist_session, "NVDA", [], wl.PermissiveResolver())
    count = watchlist_session.scalar(
        select(func.count()).select_from(WatchlistItem).where(WatchlistItem.symbol == "NVDA")
    )
    assert count == 1


def test_unit_watchlist_add_item_groups_type_and_readd_after_remove(
    watchlist_session: Session,
) -> None:
    _seeded(watchlist_session)
    resolver = Universe(types={"ZZIDX": "index"})
    item = wl.add_item(watchlist_session, "zzidx", ["fab-7", "semis"], resolver)
    assert item.symbol == "ZZIDX"
    assert (item.scored, item.type, item.groups) == (False, "index", ["fab-7", "semis"])
    wl.remove_item(watchlist_session, "ZZIDX")
    again = wl.add_item(watchlist_session, "ZZIDX", [], resolver)
    assert again.groups == []
    assert watchlist_session.get(Ticker, "ZZIDX") is not None


def test_unit_watchlist_add_unresolved_crypto_or_unknown_group_rejected(
    watchlist_session: Session,
) -> None:
    _seeded(watchlist_session)
    with pytest.raises(wl.SymbolUnresolvedError):
        wl.add_item(watchlist_session, "NOPE", [], Universe(unknown={"NOPE"}))
    with pytest.raises(wl.SymbolUnresolvedError, match="crypto"):
        wl.add_item(watchlist_session, "BTC", [], Universe(types={"BTC": "crypto"}))
    with pytest.raises(wl.WatchlistError) as caught:
        wl.add_item(watchlist_session, "ZZZ", ["no-such-group"], wl.PermissiveResolver())
    assert caught.value.errors


def test_unit_watchlist_cap_301st_item_raises_watchlist_full(watchlist_session: Session) -> None:
    _seeded(watchlist_session)
    resolver = wl.PermissiveResolver()
    start = wl.read_watchlist(watchlist_session).count
    for n in range(WATCHLIST_ITEM_CAP - start):
        wl.add_item(watchlist_session, f"Z{n}", [], resolver)
    assert wl.read_watchlist(watchlist_session).count == WATCHLIST_ITEM_CAP
    with pytest.raises(wl.WatchlistFullError, match="300"):
        wl.add_item(watchlist_session, "ONEMORE", [], resolver)
    assert wl.read_watchlist(watchlist_session).count == WATCHLIST_ITEM_CAP


def test_unit_watchlist_group_crud_create_rename_delete_group_keeps_tickers(
    watchlist_session: Session,
) -> None:
    _seeded(watchlist_session)
    group = wl.create_group(watchlist_session, "mine", "Mine", 20)
    assert group.symbols == []
    with pytest.raises(wl.AlreadyExistsError):
        wl.create_group(watchlist_session, "mine", "Again")
    with pytest.raises(wl.WatchlistError):
        wl.create_group(watchlist_session, "Bad Slug", "x" * 65)
    item = wl.set_item_groups(watchlist_session, "NVDA", ["mine"])
    assert item.groups == ["mine"]
    assert wl.set_item_groups(watchlist_session, "NVDA", []).groups == []
    wl.set_item_groups(watchlist_session, "NVDA", ["mine"])
    wl.delete_group(watchlist_session, "mine")
    view = wl.read_watchlist(watchlist_session)
    assert "NVDA" in {i.symbol for i in view.items}
    assert "mine" not in {g.slug for g in view.groups}
    with pytest.raises(wl.NotFoundError):
        wl.delete_group(watchlist_session, "mine")
    with pytest.raises(wl.NotFoundError):
        wl.set_item_groups(watchlist_session, "NOTLISTED", [])
    with pytest.raises(wl.NotFoundError):
        wl.remove_item(watchlist_session, "NOTLISTED")


def test_unit_watchlist_reads_before_seed_raise_not_found(watchlist_session: Session) -> None:
    with pytest.raises(wl.NotFoundError):
        wl.read_watchlist(watchlist_session)


def test_unit_watchlist_benchmarks_spy_qqq_ingested_even_if_removed(
    watchlist_session: Session,
) -> None:
    _seeded(watchlist_session)
    wl.remove_item(watchlist_session, "SPY")
    wl.remove_item(watchlist_session, "QQQ")
    assert "SPY" not in {i.symbol for i in wl.read_watchlist(watchlist_session).items}
    ingest = wl.symbols_to_ingest(watchlist_session)
    assert {"SPY", "QQQ"} <= set(ingest)
    assert ingest == sorted(set(ingest))
    assert watchlist_session.get(Ticker, "SPY") is not None  # row kept for bars and FKs
