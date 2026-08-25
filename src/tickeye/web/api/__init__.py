"""Versioned JSON API routes."""

from fastapi import APIRouter

from tickeye.web.api.export import router as export_router
from tickeye.web.api.health import router as health_router
from tickeye.web.api.market_data import router as market_data_router
from tickeye.web.api.policy import router as policy_router
from tickeye.web.api.portfolio import router as portfolio_router
from tickeye.web.api.risk import router as risk_router
from tickeye.web.api.scenario import router as scenario_router
from tickeye.web.api.watchlist import router as watchlist_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(export_router)
api_router.include_router(health_router)
api_router.include_router(market_data_router)
api_router.include_router(policy_router)
api_router.include_router(portfolio_router)
api_router.include_router(risk_router)
api_router.include_router(scenario_router)
api_router.include_router(watchlist_router)

__all__ = ["api_router"]
