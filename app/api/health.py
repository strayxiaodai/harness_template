"""Health check routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    """Return service health."""
    has_auto = hasattr(request.app.state, "graph_auto")
    has_step = hasattr(request.app.state, "graph_step")
    if not has_auto or not has_step:
        return {"status": "degraded", "detail": "graphs not compiled"}
    return {"status": "ok"}
