"""Thread artifact library routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.threads import ThreadSummary
from app.services.thread_artifacts import list_threads

router = APIRouter(prefix="/threads", tags=["threads"])


@router.get("", response_model=list[ThreadSummary])
async def list_thread_artifacts() -> list[ThreadSummary]:
    """List on-disk thread artifacts under app/threads/ for console attach."""
    return [ThreadSummary(**row) for row in list_threads()]
