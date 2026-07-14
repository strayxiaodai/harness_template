"""Business logic for harness graph runs."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import Request
from langgraph.types import Command

from app.db.graphs import graph_for_request, invoke_with_timeout
from app.schemas.run import ResumeRequest, RunRequest, RunResponse
from app.services.resume_overrides import apply_resume_overrides
from app.services.snapshot import snapshot_to_response
from app.services.state import initial_state
from app.services.thread_artifacts import (
    lookup_thread_dir,
    record_node_update,
    refresh_from_snapshot,
    safe_init_thread_artifacts,
)

logger = logging.getLogger(__name__)

_STAGE_NODES = ("planner", "executor", "learner", "actioner")


def _resume_input(
    snapshot: Any,
    body: ResumeRequest,
) -> object | None:
    """Build the graph input for a HITL resume.

    Dynamic ``interrupt()`` pauses must be resumed with ``Command(resume=...)``.
    Node-boundary ``interrupt_after`` pauses continue with ``None``.
    """
    interrupts = tuple(getattr(snapshot, "interrupts", None) or ())
    if body.interrupt_resume is not None:
        return Command(resume=body.interrupt_resume)
    if interrupts:
        return Command(resume=True)
    return None


def _task_label(body: RunRequest) -> str:
    """Prefer task text; fall back to skill slug for skill-only starts."""
    task = body.task.strip()
    if task:
        return task
    if body.skill_slug:
        return body.skill_slug
    return body.thread_id


def _values_from_response(response: RunResponse) -> dict[str, Any]:
    return {
        "rounds": response.rounds,
        "plan": response.plan,
        "result": response.result,
        "learning": response.learning,
        "learning_candidates": response.learning_candidates,
        "approved": response.approved,
        "refine_from": response.refine_from,
        "loop_score": response.loop_score,
        "skill_preview_ready": response.skill_preview_ready,
        "execution": response.execution,
        "tool_calls": response.tool_calls,
        "memory_cursor": response.memory_cursor,
    }


def _status_hints(response: RunResponse) -> dict[str, str]:
    hints = {node: "complete" for node in _STAGE_NODES}
    if response.needs_human and response.next_action in _STAGE_NODES:
        hints[response.next_action] = "paused"
    return hints


def _refresh_artifacts(thread_dir: Path | None, response: RunResponse) -> None:
    if thread_dir is None:
        return
    try:
        refresh_from_snapshot(
            thread_dir,
            _values_from_response(response),
            status_hints=_status_hints(response),
        )
    except OSError as exc:
        logger.warning("failed to refresh thread artifacts: %s", exc)


def _record_stream_chunk(thread_dir: Path | None, chunk: Any) -> None:
    if thread_dir is None or not isinstance(chunk, dict):
        return
    for node, patch in chunk.items():
        if node not in _STAGE_NODES or not isinstance(patch, dict):
            continue
        rounds = int(patch.get("rounds") or 1)
        try:
            record_node_update(
                thread_dir,
                node=node,
                round_num=max(rounds, 1),
                payload=patch,
                status="complete",
            )
        except OSError as exc:
            logger.warning("failed to record thread artifact for %s: %s", node, exc)


async def run_harness(request: Request, body: RunRequest) -> RunResponse:
    """Start a new harness thread and return the latest checkpoint snapshot."""
    graph = graph_for_request(request, human_in_the_loop=body.human_in_the_loop)
    config: dict[str, object] = {"configurable": {"thread_id": body.thread_id}}
    thread_dir = safe_init_thread_artifacts(
        _task_label(body),
        body.thread_id,
        body.plan,
    )

    await invoke_with_timeout(
        graph,
        initial_state(body),
        config,
        timeout_seconds=body.timeout_seconds,
    )
    response = await snapshot_to_response(graph, body.thread_id)
    _refresh_artifacts(thread_dir, response)
    return response


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
            patch = apply_resume_overrides(values, patch)
            await graph.aupdate_state(config, patch)

    await invoke_with_timeout(
        graph,
        _resume_input(snapshot, body),
        config,
        timeout_seconds=body.timeout_seconds,
    )
    response = await snapshot_to_response(graph, body.thread_id)
    _refresh_artifacts(lookup_thread_dir(body.thread_id), response)
    return response


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
    thread_dir = safe_init_thread_artifacts(
        _task_label(body),
        body.thread_id,
        body.plan,
    )

    try:
        async for chunk in graph.astream(
            initial,
            config,
            stream_mode="updates",
        ):
            _record_stream_chunk(thread_dir, chunk)
            yield f"data: {serialize_stream_chunk(chunk)}\n\n"
        snapshot = await snapshot_to_response(graph, body.thread_id)
        _refresh_artifacts(thread_dir, snapshot)
        yield f"data: {serialize_stream_chunk({'final': snapshot.model_dump()})}\n\n"
    except Exception as exc:
        logger.exception("graph stream failed for thread %s", body.thread_id)
        yield f"data: {serialize_stream_chunk({'error': str(exc)})}\n\n"
