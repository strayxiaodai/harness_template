"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.runs import router as runs_router
from app.api.skills import router as skills_router
from app.core.config import API_TITLE, CORS_ALLOW_ORIGINS
from app.db.lifespan import graph_lifespan


def create_app() -> FastAPI:
    """Build and configure the harness HTTP application."""
    app = FastAPI(
        title=API_TITLE,
        lifespan=graph_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOW_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(runs_router)
    app.include_router(skills_router)

    return app
