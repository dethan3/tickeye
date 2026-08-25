"""Manual refresh and data-quality routes."""

from typing import cast

from fastapi import APIRouter, Request

from tickeye.application.market_data_service import MarketDataService
from tickeye.web.schemas.market_data import (
    DataQualityResponse,
    MarketRefreshRequest,
    MarketRefreshResponse,
)

router = APIRouter(tags=["market-data"])


def _service(request: Request) -> MarketDataService:
    return cast(MarketDataService, request.app.state.market_data_service)


@router.get("/data-quality", response_model=DataQualityResponse)
async def get_data_quality(request: Request) -> DataQualityResponse:
    return DataQualityResponse.from_domain(_service(request).get_quality())


@router.post("/market-data/refresh", response_model=MarketRefreshResponse)
async def refresh_market_data(
    payload: MarketRefreshRequest,
    request: Request,
) -> MarketRefreshResponse:
    return MarketRefreshResponse.from_domain(
        _service(request).refresh(payload.instrument_ids)
    )
