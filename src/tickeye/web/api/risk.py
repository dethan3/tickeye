"""Current risk snapshot and explicit recalculation routes."""

from typing import cast

from fastapi import APIRouter, Request

from tickeye.application.policy_service import RiskEvaluationService
from tickeye.application.risk_service import RiskService
from tickeye.web.schemas.risk import RiskResponse

router = APIRouter(prefix="/risk", tags=["risk"])


def _service(request: Request) -> RiskService:
    return cast(RiskService, request.app.state.risk_service)


def _evaluation_service(request: Request) -> RiskEvaluationService:
    return cast(RiskEvaluationService, request.app.state.risk_evaluation_service)


@router.get("/current", response_model=RiskResponse)
async def get_current_risk(request: Request) -> RiskResponse:
    snapshot = _service(request).current()
    if snapshot is None:
        return RiskResponse.empty()
    evaluation = _evaluation_service(request).current_for_snapshot(snapshot.snapshot_id)
    return RiskResponse.from_stored(snapshot, evaluation)


@router.post("/recalculate", response_model=RiskResponse)
async def recalculate_risk(request: Request) -> RiskResponse:
    snapshot = _service(request).recalculate()
    evaluation = _evaluation_service(request).evaluate(snapshot)
    return RiskResponse.from_stored(snapshot, evaluation)
