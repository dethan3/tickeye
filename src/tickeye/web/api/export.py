"""Local user-data portability endpoint."""

from typing import cast

from fastapi import APIRouter, Request, Response

from tickeye.application.export_service import ExportService
from tickeye.web.schemas.export import UserDataExportResponse

router = APIRouter(tags=["local-data"])


@router.get("/export", response_model=UserDataExportResponse)
async def export_user_data(
    request: Request,
    response: Response,
) -> UserDataExportResponse:
    service = cast(ExportService, request.app.state.export_service)
    response.headers["Content-Disposition"] = (
        'attachment; filename="tickeye-user-data.json"'
    )
    return UserDataExportResponse.from_domain(service.export())
