"""Compiled graph accessors and invocation helpers."""

from __future__ import annotations

import asyncio

from fastapi import Request


def graph_for_request(request: Request, *, human_in_the_loop: bool) -> object:
    """Return the auto or step graph compiled at startup."""
    if human_in_the_loop:
        return request.app.state.graph_step
    return request.app.state.graph_auto


def graph_for_checkpoint(
    request: Request,
    *,
    values: dict[str, object] | None = None,
) -> object:
    """Return the graph that owns this thread's checkpoint view."""
    if values and values.get("human_in_the_loop"):
        return request.app.state.graph_step
    return request.app.state.graph_auto


async def invoke_with_timeout(
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
