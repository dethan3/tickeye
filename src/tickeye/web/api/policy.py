"""Explicit policy rules and deduplicated insight events."""

from typing import cast

from fastapi import APIRouter, Request

from tickeye.application.policy_service import PolicyService, RiskEvaluationService
from tickeye.application.risk_service import RiskService
from tickeye.web.schemas.policy import (
    EventResponse,
    PolicyResponse,
    ReplacePoliciesRequest,
)

router = APIRouter(tags=["policy"])


def _policy_service(request: Request) -> PolicyService:
    return cast(PolicyService, request.app.state.policy_service)


def _risk_service(request: Request) -> RiskService:
    return cast(RiskService, request.app.state.risk_service)


def _evaluation_service(request: Request) -> RiskEvaluationService:
    return cast(RiskEvaluationService, request.app.state.risk_evaluation_service)


@router.get("/policies", response_model=PolicyResponse)
async def get_policies(request: Request) -> PolicyResponse:
    return PolicyResponse.from_domain(_policy_service(request).get())


@router.put("/policies", response_model=PolicyResponse)
async def replace_policies(
    payload: ReplacePoliciesRequest,
    request: Request,
) -> PolicyResponse:
    policy = _policy_service(request).replace(
        payload.expected_revision,
        tuple(item.to_draft() for item in payload.rules),
    )
    snapshot = _risk_service(request).recalculate()
    _evaluation_service(request).evaluate(snapshot)
    return PolicyResponse.from_domain(policy)


@router.get("/events", response_model=EventResponse)
async def get_events(request: Request) -> EventResponse:
    return EventResponse.from_domain(_evaluation_service(request).events())
