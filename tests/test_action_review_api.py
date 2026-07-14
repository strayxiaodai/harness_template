"""API E2E: action_review interrupt → resume keep/edit/drop → memorize commit."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from graph.schemas import ActionScoreResult


CANDIDATES: list[dict[str, Any]] = [
    {
        "id": "m0",
        "content": "User prefers pytest",
        "memory_type": "preference",
        "importance": 0.8,
    },
    {
        "id": "m1",
        "content": "Project uses FastAPI",
        "memory_type": "fact",
        "importance": 0.6,
    },
]

EDITED_CONTENT = "User prefers pytest (edited)"


def _seed_values(**overrides: object) -> dict[str, Any]:
    """Minimal AgentState values for seeding past reviewer."""
    messages = [HumanMessage(content="I prefer pytest over unittest")]
    base: dict[str, Any] = {
        "thread_id": "action-review-e2e",
        "task": "Ship memory review",
        "messages": messages,
        "plan": ["extract", "review", "store"],
        "rounds": 0,
        "max_rounds": 3,
        "role": "learner",
        "approved": True,
        "human_in_the_loop": True,
        "memory_cursor": 0,
        "pending_memories": [],
        "approved_memories": [],
        "learning": {
            "verdict": "pass",
            "reason": "ok",
            "suggested_step": "finish",
            "lessons": {
                "worked": [],
                "failed": [],
                "risks": [],
                "next_time": [],
            },
        },
        "learning_candidates": [],
        "execution": {
            "summary": "done",
            "changes": [],
            "risks": [],
            "verification": ["ok"],
        },
    }
    base.update(overrides)
    return base


async def seed_action_review_interrupt(
    graph: Any,
    *,
    thread_id: str,
) -> Any:
    """Seed past learner and run until actioner's action_review interrupt."""
    config = {"configurable": {"thread_id": thread_id}}
    await graph.aupdate_state(
        config,
        _seed_values(thread_id=thread_id),
        as_node="learner",
    )
    await graph.ainvoke(None, config)
    return await graph.aget_state(config)


@pytest.fixture
def action_review_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """HITL graph with stubbed score/extract/clarification/commit."""
    pytest.importorskip("langgraph")
    from langgraph.checkpoint.memory import MemorySaver

    from agent import actioner as actioner_module
    from agent import memorize as memorize_module
    from app.main import app
    from graph.builder import compile_with_checkpointer
    from rag.ingest import memory_extract as memory_extract_module

    commit_spy = AsyncMock(
        return_value={
            "memory_cursor": 1,
            "pending_memories": [],
            "approved_memories": [],
        },
    )
    extract_stub = AsyncMock(return_value=list(CANDIDATES))
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(return_value=ActionScoreResult(score=50, rationale="ok")),
    )
    monkeypatch.setattr(actioner_module, "extract_memory_candidates", extract_stub)
    monkeypatch.setattr(
        memory_extract_module,
        "extract_memory_candidates",
        extract_stub,
    )
    if hasattr(actioner_module, "ask_clarification"):
        monkeypatch.setattr(
            actioner_module,
            "ask_clarification",
            AsyncMock(return_value=None),
        )
    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(memorize_module, "commit_approved_memories", commit_spy)
    monkeypatch.setattr(
        memorize_module,
        "load_rag_settings",
        lambda: MagicMock(enabled=True),
    )
    monkeypatch.setattr(
        memorize_module,
        "get_rag_service",
        lambda: MagicMock(save_memory_store=MagicMock()),
    )

    graph = compile_with_checkpointer(MemorySaver(), human_in_the_loop=True)
    app.state.graph_step = graph
    app.state.graph_auto = graph
    client = TestClient(app, raise_server_exceptions=True)
    client.commit_spy = commit_spy  # type: ignore[attr-defined]
    client.graph = graph  # type: ignore[attr-defined]
    return client


@pytest.mark.asyncio
async def test_action_review_resume_keeps_edits_drops_and_commits(
    action_review_client: TestClient,
) -> None:
    """Keep+edit m0, drop m1; store once; clear pending; no memorize HITL pause."""
    graph = action_review_client.graph  # type: ignore[attr-defined]
    commit_spy = action_review_client.commit_spy  # type: ignore[attr-defined]
    thread_id = "action-review-e2e"

    snap = await seed_action_review_interrupt(graph, thread_id=thread_id)
    interrupts = tuple(getattr(snap, "interrupts", None) or ())
    assert interrupts, "expected action_review interrupt before resume"
    value = getattr(interrupts[0], "value", {}) or {}
    assert value.get("kind") == "action_review"
    assert value.get("node") == "actioner"
    assert value.get("skill_preview_ready") is False
    memories = value.get("memories") or []
    assert len(memories) == 2
    assert {m["id"] for m in memories} == {"m0", "m1"}
    commit_spy.assert_not_awaited()
    # Actioner has not returned yet at dynamic interrupt; candidates live in payload.
    state_pending = (snap.values or {}).get("pending_memories")
    assert state_pending in ([], None)
    state_approved = (snap.values or {}).get("approved_memories")
    assert state_approved in ([], None)

    response = action_review_client.post(
        "/resume",
        json={
            "thread_id": thread_id,
            "interrupt_resume": {
                "memories": [
                    {
                        "id": "m0",
                        "keep": True,
                        "content": EDITED_CONTENT,
                        "memory_type": "preference",
                        "importance": 0.9,
                    },
                    {"id": "m1", "keep": False},
                ],
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body.get("interrupt") is None
    assert body.get("next_action") in (None, "")

    commit_spy.assert_awaited_once()
    call_kwargs = commit_spy.await_args.kwargs
    call_args = commit_spy.await_args.args
    approved = call_kwargs.get("approved_memories")
    if approved is None and call_args:
        state_arg = call_args[0]
        if isinstance(state_arg, dict):
            approved = state_arg.get("approved_memories")
    assert approved is not None
    assert len(approved) == 1
    assert approved[0]["content"] == EDITED_CONTENT
    assert all(row.get("content") != "Project uses FastAPI" for row in approved)

    final = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    values = final.values or {}
    assert values.get("pending_memories") in ([], None)
    assert values.get("approved_memories") in ([], None)
    assert values.get("memory_cursor") == len(values.get("messages") or [])
    assert not (getattr(final, "interrupts", None) or ())
    assert not (final.next or ())
