"""Stable JSON error responses for all API consumers."""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from tickeye.application.errors import (
    DuplicateImportError,
    PortfolioConflictError,
    PortfolioValidationError,
)
from tickeye.application.market_data_service import MarketDataSelectionError
from tickeye.application.policy_service import (
    PolicyRevisionConflictError,
    PolicyValidationError,
)
from tickeye.application.scenario_service import (
    ScenarioNotFoundError,
    ScenarioValidationError,
)
from tickeye.application.watchlist_service import (
    WatchlistConflictError,
    WatchlistNotFoundError,
    WatchlistValidationError,
)

logger = logging.getLogger(__name__)


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(
        status_code=status_code,
        content={"error": error},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register public errors without exposing stack traces or input data."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="The request is invalid.",
            details=[
                {
                    "code": error["type"],
                    "message": error["msg"],
                    "field": ".".join(str(part) for part in error["loc"]),
                }
                for error in _exc.errors()
            ],
        )

    @app.exception_handler(PortfolioValidationError)
    async def portfolio_validation_error_handler(
        _request: Request,
        exc: PortfolioValidationError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="portfolio_validation_error",
            message="Portfolio data is invalid.",
            details=[
                {
                    "code": issue.code,
                    "message": issue.message,
                    "field": issue.field,
                    "row": issue.row,
                }
                for issue in exc.issues
            ],
        )

    @app.exception_handler(PortfolioConflictError)
    async def portfolio_conflict_error_handler(
        _request: Request,
        _exc: PortfolioConflictError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="portfolio_revision_conflict",
            message="Portfolio changed after it was loaded. Reload before saving.",
        )

    @app.exception_handler(DuplicateImportError)
    async def duplicate_import_error_handler(
        _request: Request,
        _exc: DuplicateImportError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="duplicate_portfolio_import",
            message="This CSV batch was already imported.",
        )

    @app.exception_handler(MarketDataSelectionError)
    async def market_data_selection_error_handler(
        _request: Request,
        exc: MarketDataSelectionError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="unknown_market_data_instruments",
            message="Some selected instruments are neither held nor watched.",
            details=[
                {
                    "code": "unknown_instrument_id",
                    "message": "The instrument is neither held nor watched.",
                    "field": "instrument_ids",
                    "instrument_id": instrument_id,
                }
                for instrument_id in sorted(exc.unknown_ids)
            ],
        )

    @app.exception_handler(PolicyRevisionConflictError)
    async def policy_revision_conflict_handler(
        _request: Request,
        _exc: PolicyRevisionConflictError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="policy_revision_conflict",
            message="Risk policies changed after they were loaded. Reload before saving.",
        )

    @app.exception_handler(PolicyValidationError)
    async def policy_validation_error_handler(
        _request: Request,
        exc: PolicyValidationError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="policy_validation_error",
            message="Risk policies are invalid.",
            details=[
                {"code": "invalid_policy", "message": message, "field": "rules"}
                for message in exc.messages
            ],
        )

    @app.exception_handler(ScenarioValidationError)
    async def scenario_validation_error_handler(
        _request: Request,
        exc: ScenarioValidationError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="scenario_validation_error",
            message="Scenario operation is invalid.",
            details=[
                {
                    "code": exc.code,
                    "message": exc.message,
                    "field": "operation",
                }
            ],
        )

    @app.exception_handler(ScenarioNotFoundError)
    async def scenario_not_found_handler(
        _request: Request,
        _exc: ScenarioNotFoundError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="scenario_not_found",
            message="The requested Scenario does not exist.",
        )

    @app.exception_handler(WatchlistValidationError)
    async def watchlist_validation_error_handler(
        _request: Request,
        exc: WatchlistValidationError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="watchlist_validation_error",
            message="Watchlist data is invalid.",
            details=[
                {"code": exc.code, "message": exc.message, "field": exc.field}
            ],
        )

    @app.exception_handler(WatchlistConflictError)
    async def watchlist_conflict_error_handler(
        _request: Request,
        exc: WatchlistConflictError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            code=exc.code,
            message=exc.message,
        )

    @app.exception_handler(WatchlistNotFoundError)
    async def watchlist_not_found_error_handler(
        _request: Request,
        _exc: WatchlistNotFoundError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="watchlist_not_found",
            message="The requested watchlist or item does not exist.",
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "The request failed."
        return _error_response(
            status_code=exc.status_code,
            code="http_error",
            message=message,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled request error", exc_info=exc)
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="An unexpected error occurred.",
        )
