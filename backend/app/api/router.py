"""Aggregates every route module under a single router."""

from fastapi import APIRouter

from app.api.routes import ai, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(ai.router)
