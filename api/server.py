"""FastAPI service for the LangGraph harness."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from api.schemas import (
    DistillSkillRequest,
    DistillSkillResponse,
    ResumeRequest,
    RunRequest,
    RunResponse,
    SaveSkillRequest,
    SkillDetail,
    SkillSummary,
)
from memory.checkpoint import graph_lifespan
from skills.distill import SkillNotEligibleError, distill_skill_from_thread, save_skill_draft
from skills.store import list_skills, normalize_slug, read_meta, read_skill, skill_path

logger = logging.getLogger(__name__)

api = FastAPI(
    title="Enterprise LangGraph Harness",
    lifespan=graph_lifespan,
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _initial_state(request: RunRequest) -> dict[str, object]:
    """Build the starting graph state for a new thread."""
    task = request.task.strip()
    state: dict[str, object] = {
        "thread_id": request.thread_id,
        "task": task,
        "messages": [],
        "plan": request.plan,
        "rounds": 0,
        "max_rounds": request.max_rounds,
        "role": "",
        "approved": False,
        "human_in_the_loop": request.human_in_the_loop,
    }

    if request.skill_slug:
        slug = normalize_slug(request.skill_slug)
        name, description, body = read_skill(slug)
        if not task:
            task = f"Apply skill: {description}"
            state["task"] = task
        state["skill_slug"] = slug
        state["skill_context"] = body
        logger.info("Loaded harness skill %s (%s) for thread %s", slug, name, request.thread_id)

    return state


async def _snapshot_to_response(
    graph: object,
    thread_id: str,
) -> RunResponse:
    """Translate the latest checkpoint into an API response."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await graph.aget_state(config)
    next_nodes = tuple(snapshot.next or ())
    values = snapshot.values or {}
    hitl = bool(values.get("human_in_the_loop", False))
    needs_human = hitl and bool(next_nodes)

    return RunResponse(
        thread_id=thread_id,
        status="awaiting_human" if needs_human else "complete",
        approved=bool(values.get("approved", False)),
        needs_human=needs_human,
        result=values.get("result"),
        next_action=next_nodes[0] if next_nodes else None,
        last_role=str(values.get("role", "")) or None,
        rounds=int(values.get("rounds", 0)),
        max_rounds=int(values.get("max_rounds", 0)),
    )


def _graph_for_request(request: Request, *, human_in_the_loop: bool) -> object:
    """Return the auto or step graph compiled at startup."""
    if human_in_the_loop:
        return request.app.state.graph_step
    return request.app.state.graph_auto


async def _invoke_with_timeout(
    graph: object,
    state: dict[str, object] | None,
    config: dict[str, object],
    *,
    timeout_seconds: float,
) -> None:
    """Invoke the graph with a wall-clock timeout."""
    await asyncio.wait_for(
        graph.ainvoke(state, config),
        timeout=timeout_seconds,
    )


@api.get("/health")
async def health(request: Request) -> dict[str, str]:
    """Return service health."""
    has_auto = hasattr(request.app.state, "graph_auto")
    has_step = hasattr(request.app.state, "graph_step")
    if not has_auto or not has_step:
        return {"status": "degraded", "detail": "graphs not compiled"}
    return {"status": "ok"}


@api.post("/run", response_model=RunResponse)
async def run_agent(request: Request, body: RunRequest) -> RunResponse:
    """Start or continue a graph run for the given thread."""
    graph = _graph_for_request(request, human_in_the_loop=body.human_in_the_loop)
    config: dict[str, object] = {"configurable": {"thread_id": body.thread_id}}

    try:
        await _invoke_with_timeout(
            graph,
            _initial_state(body),
            config,
            timeout_seconds=body.timeout_seconds,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="graph run timed out") from exc
    except Exception as exc:
        logger.exception("graph run failed for thread %s", body.thread_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return await _snapshot_to_response(graph, body.thread_id)


@api.post("/resume", response_model=RunResponse)
async def resume_agent(request: Request, body: ResumeRequest) -> RunResponse:
    """Resume a human-in-the-loop thread."""
    config: dict[str, object] = {"configurable": {"thread_id": body.thread_id}}
    graph = request.app.state.graph_step
    snapshot = await graph.aget_state(config)
    values = snapshot.values or {}

    if not values.get("human_in_the_loop"):
        raise HTTPException(
            status_code=409,
            detail="thread was not started in human-in-the-loop mode",
        )

    if body.overrides is not None:
        patch = body.overrides.model_dump(exclude_none=True)
        if patch:
            await graph.aupdate_state(config, patch)

    try:
        await _invoke_with_timeout(
            graph,
            None,
            config,
            timeout_seconds=body.timeout_seconds,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="graph resume timed out") from exc
    except Exception as exc:
        logger.exception("graph resume failed for thread %s", body.thread_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return await _snapshot_to_response(graph, body.thread_id)


def _serialize_stream_chunk(chunk: Any) -> str:
    """Serialize a stream chunk to SSE data."""
    return json.dumps(chunk, default=str)


@api.post("/stream")
async def stream_agent(request: Request, body: RunRequest) -> StreamingResponse:
    """Stream graph updates for a run (Server-Sent Events)."""
    graph = _graph_for_request(request, human_in_the_loop=body.human_in_the_loop)
    config: dict[str, object] = {"configurable": {"thread_id": body.thread_id}}
    initial_state = _initial_state(body)

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for chunk in graph.astream(
                initial_state,
                config,
                stream_mode="updates",
            ):
                yield f"data: {_serialize_stream_chunk(chunk)}\n\n"
            snapshot = await _snapshot_to_response(graph, body.thread_id)
            yield f"data: {_serialize_stream_chunk({'final': snapshot.model_dump()})}\n\n"
        except Exception as exc:
            logger.exception("graph stream failed for thread %s", body.thread_id)
            yield f"data: {_serialize_stream_chunk({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


def _graph_for_checkpoint(request: Request) -> object:
    """Return a graph that shares the harness checkpointer."""
    return request.app.state.graph_auto


@api.get("/skills", response_model=list[SkillSummary])
async def list_distilled_skills() -> list[SkillSummary]:
    """List skills distilled from prior harness threads."""
    return [
        SkillSummary(
            slug=item.slug,
            name=item.name,
            description=item.description,
            path=item.path,
            thread_count=item.thread_count,
            updated_at=item.updated_at.isoformat() if item.updated_at else None,
        )
        for item in list_skills()
    ]


@api.get("/skills/{slug}", response_model=SkillDetail)
async def get_distilled_skill(slug: str) -> SkillDetail:
    """Return a saved skill playbook for manual runs from the console."""
    normalized = normalize_slug(slug)
    try:
        name, description, body = read_skill(normalized)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    meta = read_meta(normalized)
    updated_at = meta.distilled_at[-1] if meta.distilled_at else None
    return SkillDetail(
        slug=normalized,
        name=name,
        description=description,
        path=str(skill_path(normalized)),
        body=body,
        thread_count=len(meta.thread_ids),
        updated_at=updated_at,
    )


@api.post("/skills/distill", response_model=DistillSkillResponse)
async def distill_skill(
    request: Request,
    body: DistillSkillRequest,
) -> DistillSkillResponse:
    """Distill a thread into a skill draft; set save=true to write immediately."""
    graph = _graph_for_checkpoint(request)
    try:
        result = await distill_skill_from_thread(
            graph,
            thread_id=body.thread_id,
            name=body.name,
            refine=body.refine,
            save=body.save,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SkillNotEligibleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("skill distill failed for thread %s", body.thread_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _distill_response(result)


@api.post("/skills/save", response_model=DistillSkillResponse)
async def save_skill(
    request: Request,
    body: SaveSkillRequest,
) -> DistillSkillResponse:
    """Persist a previewed skill draft to .cursor/skills/."""
    graph = _graph_for_checkpoint(request)
    try:
        result = await save_skill_draft(
            graph,
            thread_id=body.thread_id,
            slug=body.slug,
            name=body.name,
            description=body.description,
            body=body.body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SkillNotEligibleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("skill save failed for thread %s", body.thread_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _distill_response(result)


def _distill_response(result: object) -> DistillSkillResponse:
    """Map internal distill result to API response."""
    from skills.schemas import DistillSkillResponse as InternalResponse

    internal = InternalResponse.model_validate(result)
    return DistillSkillResponse(
        thread_id=internal.thread_id,
        slug=internal.slug,
        path=internal.path,
        saved=internal.saved,
        created=internal.created,
        refined=internal.refined,
        description=internal.description,
        name=internal.name,
        body=internal.body,
        status=internal.status,
    )
