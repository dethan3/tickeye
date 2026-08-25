"""Scenario experiment routes."""

from typing import cast

from fastapi import APIRouter, Request

from tickeye.application.scenario_service import ScenarioService
from tickeye.web.schemas.scenario import (
    AddScenarioOperationRequest,
    CreateScenarioRequest,
    ScenarioComparisonResponse,
    ScenarioListResponse,
)

router = APIRouter(prefix="/scenarios", tags=["scenario"])


def _service(request: Request) -> ScenarioService:
    return cast(ScenarioService, request.app.state.scenario_service)


@router.get("", response_model=ScenarioListResponse)
async def list_scenarios(request: Request) -> ScenarioListResponse:
    return ScenarioListResponse.from_domain(_service(request).list())


@router.post("", response_model=ScenarioComparisonResponse)
async def create_scenario(
    payload: CreateScenarioRequest,
    request: Request,
) -> ScenarioComparisonResponse:
    _summary, comparison = _service(request).create(
        payload.name,
        tuple(item.to_domain() for item in payload.stress_assumptions),
        payload.candidate_instrument_id,
    )
    return ScenarioComparisonResponse.from_domain(comparison)


@router.post("/{scenario_id}/operations", response_model=ScenarioComparisonResponse)
async def add_scenario_operation(
    scenario_id: int,
    payload: AddScenarioOperationRequest,
    request: Request,
) -> ScenarioComparisonResponse:
    comparison = _service(request).append_operation(scenario_id, payload.to_domain())
    return ScenarioComparisonResponse.from_domain(comparison)


@router.get("/{scenario_id}/comparison", response_model=ScenarioComparisonResponse)
async def get_scenario_comparison(
    scenario_id: int,
    request: Request,
) -> ScenarioComparisonResponse:
    return ScenarioComparisonResponse.from_domain(
        _service(request).comparison(scenario_id)
    )
