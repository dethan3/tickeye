"""User-curated watchlist routes."""

from typing import cast

from fastapi import APIRouter, Request, status

from tickeye.application.watchlist_service import WatchlistService
from tickeye.web.schemas.watchlist import (
    CreateWatchlistRequest,
    UpdateWatchlistItemRequest,
    WatchlistItemInput,
    WatchlistResponse,
)

router = APIRouter(prefix="/watchlists", tags=["watchlist"])


def _service(request: Request) -> WatchlistService:
    return cast(WatchlistService, request.app.state.watchlist_service)


@router.get("", response_model=WatchlistResponse)
async def list_watchlists(request: Request) -> WatchlistResponse:
    return WatchlistResponse.from_domain(_service(request).list())


@router.post("", response_model=WatchlistResponse)
async def create_watchlist(
    payload: CreateWatchlistRequest,
    request: Request,
) -> WatchlistResponse:
    return WatchlistResponse.from_domain(_service(request).create(payload.name))


@router.delete("/{watchlist_id}", response_model=WatchlistResponse)
async def delete_watchlist(
    watchlist_id: int,
    request: Request,
) -> WatchlistResponse:
    return WatchlistResponse.from_domain(_service(request).delete(watchlist_id))


@router.post(
    "/{watchlist_id}/items",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_watchlist_item(
    watchlist_id: int,
    payload: WatchlistItemInput,
    request: Request,
) -> WatchlistResponse:
    return WatchlistResponse.from_domain(
        _service(request).add_item(watchlist_id, payload.to_domain())
    )


@router.put("/{watchlist_id}/items/{item_id}", response_model=WatchlistResponse)
async def update_watchlist_item(
    watchlist_id: int,
    item_id: int,
    payload: UpdateWatchlistItemRequest,
    request: Request,
) -> WatchlistResponse:
    return WatchlistResponse.from_domain(
        _service(request).update_item(
            watchlist_id,
            item_id,
            payload.reason,
            tuple(payload.tags),
        )
    )


@router.delete("/{watchlist_id}/items/{item_id}", response_model=WatchlistResponse)
async def remove_watchlist_item(
    watchlist_id: int,
    item_id: int,
    request: Request,
) -> WatchlistResponse:
    return WatchlistResponse.from_domain(
        _service(request).remove_item(watchlist_id, item_id)
    )
