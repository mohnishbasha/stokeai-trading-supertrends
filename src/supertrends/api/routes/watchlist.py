# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Watchlist endpoints under /api/v1 (ARCHITECTURE 6.1, ADR-019, ADR-025).

Reads are open; writes need the bearer token. Errors are RFC 9457 problem+json. The
route class below renders them for this router so the module works with or without the
app-wide handlers added by S1-T08.
"""

import secrets
from collections.abc import Callable, Coroutine, Iterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from supertrends.api.schemas.watchlist import (
    AddItemRequest,
    CreateGroupRequest,
    GroupResponse,
    ItemResponse,
    SetGroupsRequest,
    WatchlistResponse,
)
from supertrends.api.security import require_write_token
from supertrends.data import watchlist as service
from supertrends.data.db import session_scope
from supertrends.data.watchlist import SymbolResolver, WatchlistError

PROBLEM_TYPE_PREFIX = "urn:supertrends:problem:"
PROBLEM_CONTENT_TYPE = "application/problem+json"
_BAD_JSON = "json_invalid"


def _problem(  # noqa: PLR0913, PLR0917 (flat helper)
    request: Request,
    status: int,
    slug: str,
    title: str,
    detail: str,
    errors: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or request.headers.get(
        "x-request-id", secrets.token_hex(8)
    )
    body: dict[str, Any] = {
        "type": f"{PROBLEM_TYPE_PREFIX}{slug}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "request_id": request_id,
    }
    if errors is not None:
        body["errors"] = errors
    out = {"X-Request-ID": request_id, **(headers or {})}
    return JSONResponse(body, status_code=status, media_type=PROBLEM_CONTENT_TYPE, headers=out)


class ProblemRoute(APIRoute):
    """Route class that turns domain, validation, and auth errors into problem+json."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """Wrap the default handler with problem+json error rendering."""
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except WatchlistError as exc:
                return _problem(request, exc.status, exc.slug, exc.title, exc.detail, exc.errors)
            except RequestValidationError as exc:
                found = exc.errors()
                if any(e["type"] == _BAD_JSON for e in found):
                    return _problem(
                        request,
                        400,
                        "bad-request",
                        "Malformed request",
                        "request body is not valid JSON",
                    )
                errors = [{"loc": list(e["loc"]), "msg": str(e["msg"])} for e in found]
                return _problem(
                    request,
                    422,
                    "validation-error",
                    "Invalid request",
                    "request validation failed",
                    errors,
                )
            except HTTPException as exc:
                if exc.status_code != 401:
                    raise
                return _problem(
                    request,
                    401,
                    "unauthorized",
                    "Unauthorized",
                    "a valid bearer token is required",
                    headers=dict(exc.headers or {}),
                )

        return handler


router = APIRouter(prefix="/api/v1", route_class=ProblemRoute, tags=["watchlist"])


def get_session() -> Iterator[Session]:
    """A request-scoped database session (the routes commit explicitly)."""
    with session_scope() as session:
        yield session


def get_symbol_resolver() -> SymbolResolver:
    """Symbol validation. The regex alone is the check until a provider registry is wired in."""
    return service.PermissiveResolver()


def _no_query(request: Request) -> None:
    if request.query_params:
        names = ", ".join(sorted(set(request.query_params)))
        raise WatchlistError(
            f"unknown query parameter: {names}",
            [
                {"loc": ["query", n], "msg": "unknown query parameter"}
                for n in sorted(set(request.query_params))
            ],
        )


def _item(view: service.ItemView) -> ItemResponse:
    return ItemResponse(**view.__dict__)


@router.get("/watchlist", response_model=WatchlistResponse)
def get_watchlist(request: Request, session: Session = Depends(get_session)) -> WatchlistResponse:  # noqa: B008
    """The default watchlist with groups, items, and benchmarks. No token."""
    _no_query(request)
    view = service.read_watchlist(session)
    return WatchlistResponse(
        id=view.id,
        name=view.name,
        count=view.count,
        max=view.max,
        groups=[GroupResponse(**g.__dict__) for g in view.groups],
        items=[_item(i) for i in view.items],
        benchmarks=view.benchmarks,
    )


@router.post(
    "/watchlist/items",
    status_code=201,
    response_model=ItemResponse,
    dependencies=[Depends(require_write_token)],
)
def add_item(
    body: AddItemRequest,
    response: Response,
    session: Session = Depends(get_session),  # noqa: B008
    resolver: SymbolResolver = Depends(get_symbol_resolver),  # noqa: B008
) -> ItemResponse:
    """Add a symbol, optionally to existing groups."""
    view = service.add_item(session, body.symbol, body.groups, resolver)
    session.commit()
    response.headers["Location"] = "/api/v1/watchlist"
    return _item(view)


@router.delete(
    "/watchlist/items/{symbol}",
    status_code=204,
    dependencies=[Depends(require_write_token)],
)
def remove_item(symbol: str, session: Session = Depends(get_session)) -> Response:  # noqa: B008
    """Remove an item and its memberships; history is kept."""
    service.remove_item(session, symbol)
    session.commit()
    return Response(status_code=204)


@router.put(
    "/watchlist/items/{symbol}/groups",
    response_model=ItemResponse,
    dependencies=[Depends(require_write_token)],
)
def put_item_groups(
    symbol: str,
    body: SetGroupsRequest,
    session: Session = Depends(get_session),  # noqa: B008
) -> ItemResponse:
    """Replace an item's group memberships."""
    view = service.set_item_groups(session, symbol, body.groups)
    session.commit()
    return _item(view)


@router.post(
    "/watchlist/groups",
    status_code=201,
    response_model=GroupResponse,
    dependencies=[Depends(require_write_token)],
)
def create_group(
    body: CreateGroupRequest,
    session: Session = Depends(get_session),  # noqa: B008
) -> GroupResponse:
    """Create a named group."""
    view = service.create_group(session, body.slug, body.name, body.position)
    session.commit()
    return GroupResponse(**view.__dict__)


@router.delete(
    "/watchlist/groups/{slug}",
    status_code=204,
    dependencies=[Depends(require_write_token)],
)
def delete_group(slug: str, session: Session = Depends(get_session)) -> Response:  # noqa: B008
    """Delete a group and its memberships, never its items."""
    service.delete_group(session, slug)
    session.commit()
    return Response(status_code=204)
