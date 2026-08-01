"""Aggregates every route module under a single router."""

from fastapi import APIRouter

from app.api.routes import ai, cases, health, matching, tasks

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(ai.router)
api_router.include_router(tasks.router)
api_router.include_router(matching.router)
api_router.include_router(cases.router)
