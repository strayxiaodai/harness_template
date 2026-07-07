"""Harness run, resume, and stream routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.schemas.run import ResumeRequest, RunRequest, RunResponse
from app.services.harness import resume_harness, run_harness, stream_harness

logger = logging.getLogger(__name__)

router = APIRouter(tags=["runs"])


@router.post("/run", response_model=RunResponse)
async def run_agent(request: Request, body: RunRequest) -> RunResponse:
    """Start or continue a graph run for the given thread."""
    try:
        return await run_harness(request, body)
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="graph run timed out") from exc
    except Exception as exc:
        logger.exception("graph run failed for thread %s", body.thread_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/resume", response_model=RunResponse)
async def resume_agent(request: Request, body: ResumeRequest) -> RunResponse:
    """Resume a human-in-the-loop thread."""
    try:
        return await resume_harness(request, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="graph resume timed out") from exc
    except Exception as exc:
        logger.exception("graph resume failed for thread %s", body.thread_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stream")
async def stream_agent(request: Request, body: RunRequest) -> StreamingResponse:
    """Stream graph updates for a run (Server-Sent Events)."""
    return StreamingResponse(
        stream_harness(request, body),
        media_type="text/event-stream",
    )
