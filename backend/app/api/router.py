"""Aggregates every route module under a single router."""

from fastapi import APIRouter

from app.api.routes import (
    ai,
    cases,
    categories,
    dashboard,
    health,
    matching,
    tasks,
    vendor,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(categories.router)
api_router.include_router(ai.router)
api_router.include_router(tasks.router)
api_router.include_router(matching.router)
api_router.include_router(cases.router)
api_router.include_router(vendor.router)
api_router.include_router(dashboard.router)
