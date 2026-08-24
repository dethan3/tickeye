"""Versioned JSON API routes."""

from fastapi import APIRouter

from tickeye.web.api.health import router as health_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)

__all__ = ["api_router"]
