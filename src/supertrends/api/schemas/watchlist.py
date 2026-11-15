# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Watchlist request and response schemas (ARCHITECTURE 6.1)."""

import datetime as dt
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from supertrends.data.watchlist import (
    GROUP_NAME_MAX,
    SLUG_RE,
    SYMBOL_PATTERN,
    WatchlistError,
    normalize_symbol,
)


def _symbol(value: str) -> str:
    try:
        return normalize_symbol(value)
    except WatchlistError as exc:
        raise ValueError(exc.detail) from exc


def _slug(value: str) -> str:
    if not SLUG_RE.fullmatch(value):
        msg = "slug must match ^[a-z0-9][a-z0-9-]{0,47}$"
        raise ValueError(msg)
    return value


Symbol = Annotated[str, AfterValidator(_symbol), Field(description=SYMBOL_PATTERN)]
Slug = Annotated[str, AfterValidator(_slug)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AddItemRequest(_Strict):
    """Body of POST /watchlist/items."""

    symbol: Symbol
    groups: list[Slug] = Field(default_factory=list)


class SetGroupsRequest(_Strict):
    """Body of PUT /watchlist/items/{symbol}/groups."""

    groups: list[Slug]


class CreateGroupRequest(_Strict):
    """Body of POST /watchlist/groups."""

    slug: Slug
    name: Annotated[str, StringConstraints(min_length=1, max_length=GROUP_NAME_MAX)]
    position: Annotated[int, Field(ge=0)] = 0


class ItemResponse(BaseModel):
    """A watchlist item."""

    symbol: str
    name: str | None
    type: str
    scored: bool
    resolution: str
    resolution_reason: str | None
    added_at: dt.datetime
    groups: list[str]


class GroupResponse(BaseModel):
    """A watchlist group."""

    slug: str
    name: str
    position: int
    symbols: list[str]


class WatchlistResponse(BaseModel):
    """GET /watchlist."""

    id: int
    name: str
    count: int
    max: int
    groups: list[GroupResponse]
    items: list[ItemResponse]
    benchmarks: list[str]
