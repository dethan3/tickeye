"""Portfolio fact and strict CSV import endpoints."""

from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Request

from tickeye.application.errors import PortfolioValidationError, ValidationIssue
from tickeye.application.portfolio_service import PortfolioService
from tickeye.web.schemas.portfolio import (
    ImportConfirmedResponse,
    ImportPreviewResponse,
    PortfolioImportRequest,
    PortfolioResponse,
    ReplacePositionsRequest,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _service(request: Request) -> PortfolioService:
    return cast(PortfolioService, request.app.state.portfolio_service)


@router.get("", response_model=PortfolioResponse)
async def get_portfolio(request: Request) -> PortfolioResponse:
    portfolio = _service(request).get_portfolio()
    return PortfolioResponse.from_domain(portfolio, calculated_at=datetime.now(UTC))


@router.put("/positions", response_model=PortfolioResponse)
async def replace_positions(
    payload: ReplacePositionsRequest,
    request: Request,
) -> PortfolioResponse:
    portfolio = _service(request).replace_positions(
        expected_revision=payload.expected_revision,
        positions=tuple(item.to_domain() for item in payload.positions),
    )
    return PortfolioResponse.from_domain(portfolio, calculated_at=datetime.now(UTC))


@router.post(
    "/import",
    response_model=ImportPreviewResponse | ImportConfirmedResponse,
)
async def import_portfolio(
    payload: PortfolioImportRequest,
    request: Request,
) -> ImportPreviewResponse | ImportConfirmedResponse:
    service = _service(request)
    if payload.mode == "preview":
        return ImportPreviewResponse.from_domain(service.preview_csv(payload.csv_content))
    if payload.preview_token is None or payload.expected_revision is None:
        raise PortfolioValidationError(
            [
                ValidationIssue(
                    "confirmation_required",
                    "确认导入需要 preview_token 和 expected_revision。",
                )
            ]
        )
    portfolio = service.confirm_csv(
        content=payload.csv_content,
        preview_token=payload.preview_token,
        expected_revision=payload.expected_revision,
    )
    return ImportConfirmedResponse(
        portfolio=PortfolioResponse.from_domain(portfolio, calculated_at=datetime.now(UTC))
    )
