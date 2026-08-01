"""FastAPI application entrypoint."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="AI 智慧管家：智慧社區生活需求理解與服務媒合平台",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/", tags=["system"], summary="Service banner")
def root() -> dict[str, str]:
    return {
        "service": settings.PROJECT_NAME,
        "docs": "/docs",
        "health": f"{settings.API_PREFIX}/health",
    }
