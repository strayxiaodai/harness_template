"""Business logic for harness graph runs."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request

from app.db.graphs import graph_for_request, invoke_with_timeout
from app.schemas.run import ResumeRequest, RunRequest, RunResponse
from app.services.snapshot import snapshot_to_response
from app.services.state import initial_state

logger = logging.getLogger(__name__)


async def run_harness(request: Request, body: RunRequest) -> RunResponse:
    """Start a new harness thread and return the latest checkpoint snapshot."""
    graph = graph_for_request(request, human_in_the_loop=body.human_in_the_loop)
    config: dict[str, object] = {"configurable": {"thread_id": body.thread_id}}

    await invoke_with_timeout(
        graph,
        initial_state(body),
        config,
        timeout_seconds=body.timeout_seconds,
    )
    return await snapshot_to_response(graph, body.thread_id)


async def resume_harness(request: Request, body: ResumeRequest) -> RunResponse:
    """Resume a human-in-the-loop harness thread."""
    config: dict[str, object] = {"configurable": {"thread_id": body.thread_id}}
    graph = request.app.state.graph_step
    snapshot = await graph.aget_state(config)
    values = snapshot.values or {}

    if not values.get("human_in_the_loop"):
        msg = "thread was not started in human-in-the-loop mode"
        raise ValueError(msg)

    if body.overrides is not None:
        patch = body.overrides.model_dump(exclude_none=True)
        if patch:
            await graph.aupdate_state(config, patch)

    await invoke_with_timeout(
        graph,
        None,
        config,
        timeout_seconds=body.timeout_seconds,
    )
    return await snapshot_to_response(graph, body.thread_id)


def serialize_stream_chunk(chunk: Any) -> str:
    """Serialize a stream chunk to SSE data."""
    return json.dumps(chunk, default=str)


async def stream_harness(
    request: Request,
    body: RunRequest,
) -> AsyncIterator[str]:
    """Yield Server-Sent Events for a harness graph run."""
    graph = graph_for_request(request, human_in_the_loop=body.human_in_the_loop)
    config: dict[str, object] = {"configurable": {"thread_id": body.thread_id}}
    initial = initial_state(body)

    try:
        async for chunk in graph.astream(
            initial,
            config,
            stream_mode="updates",
        ):
            yield f"data: {serialize_stream_chunk(chunk)}\n\n"
        snapshot = await snapshot_to_response(graph, body.thread_id)
        yield f"data: {serialize_stream_chunk({'final': snapshot.model_dump()})}\n\n"
    except Exception as exc:
        logger.exception("graph stream failed for thread %s", body.thread_id)
        yield f"data: {serialize_stream_chunk({'error': str(exc)})}\n\n"
