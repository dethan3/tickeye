"""Application and database readiness endpoint."""

import logging
from typing import Literal, cast

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from tickeye import __version__

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["system"])


class ComponentHealth(BaseModel):
    """Status of one dependency checked by the API."""

    status: Literal["ok", "error"]


class HealthResponse(BaseModel):
    """Public readiness response consumed by the local frontend."""

    status: Literal["ok", "degraded"]
    service: str
    version: str
    database: ComponentHealth


@router.get("", response_model=HealthResponse)
async def get_health(request: Request, response: Response) -> HealthResponse:
    """Verify that the API process can execute a database query."""

    engine = cast(Engine, request.app.state.engine)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Database readiness check failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="degraded",
            service="tickeye-api",
            version=__version__,
            database=ComponentHealth(status="error"),
        )

    return HealthResponse(
        status="ok",
        service="tickeye-api",
        version=__version__,
        database=ComponentHealth(status="ok"),
    )
