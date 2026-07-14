"""Tests for the actioner agent node."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from graph.schemas import ActionScoreResult
from skills.eligibility import SKILL_PREVIEW_SCORE_THRESHOLD


PENDING_MEMORY = {
    "id": "m0",
    "content": "User prefers pytest -v for focused verification.",
    "memory_type": "preference",
    "importance": 0.8,
}

PASS_LEARNING = {
    "verdict": "pass",
    "reason": "looks good",
    "suggested_step": "finish",
    "lessons": {
        "worked": ["verification ran"],
        "failed": [],
        "risks": [],
        "next_time": [],
    },
}


@pytest.fixture(autouse=True)
def clear_pending_cache() -> Iterator[None]:
    """Keep actioner cache state isolated across tests."""
    from agent.memory_review import clear_pending

    for cursor in (None, 0, 7):
        clear_pending("test-thread", cursor)
    yield
    for cursor in (None, 0, 7):
        clear_pending("test-thread", cursor)


def _state(**overrides: object) -> dict[str, Any]:
    """Build a minimal AgentState dict for actioner tests."""
    base: dict[str, Any] = {
        "thread_id": "test-thread",
        "task": "Implement feature",
        "messages": [],
        "plan": ["step one"],
        "rounds": 0,
        "max_rounds": 3,
        "role": "actioner",
        "approved": True,
        "human_in_the_loop": False,
        "memory_cursor": 0,
        "learning": dict(PASS_LEARNING),
        "learning_candidates": [],
        "execution": {
            "summary": "implemented feature",
            "changes": ["added tests"],
            "risks": [],
            "verification": ["pytest passes"],
        },
    }
    base.update(overrides)
    return base


def _stub_commit(monkeypatch: pytest.MonkeyPatch, actioner_module: Any) -> AsyncMock:
    """Stub commit to echo approved/pending clear."""
    commit = AsyncMock(
        side_effect=lambda state: {
            "memory_cursor": len(state.get("messages") or []),
            "pending_memories": [],
            "approved_memories": [],
            "_seen_approved": list(state.get("approved_memories") or []),
            "_seen_pending": list(state.get("pending_memories") or []),
        },
    )
    monkeypatch.setattr(actioner_module, "commit_round_memories", commit)
    return commit


@pytest.mark.asyncio
async def test_actioner_soft_skips_when_not_approved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail path skips score, extract, interrupt, and commit."""
    from app.agents import actioner as actioner_module

    score = AsyncMock()
    extract = AsyncMock()
    commit = AsyncMock()
    interrupt = MagicMock()
    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(actioner_module, "score_loop", score)
    monkeypatch.setattr(actioner_module, "extract_memory_candidates", extract)
    monkeypatch.setattr(actioner_module, "commit_round_memories", commit)
    monkeypatch.setattr(actioner_module, "interrupt", interrupt)

    result = await actioner_module.actioner_agent(
        _state(
            approved=False,
            learning={
                "verdict": "fail",
                "reason": "incomplete",
                "suggested_step": "planner",
                "lessons": {
                    "worked": [],
                    "failed": ["missing tests"],
                    "risks": [],
                    "next_time": [],
                },
            },
        ),
    )

    score.assert_not_awaited()
    extract.assert_not_awaited()
    commit.assert_not_awaited()
    interrupt.assert_not_called()
    assert result["loop_score"] == 0
    assert result["skill_preview_ready"] is False
    assert result["refine_from"] == "planner"
    assert result["rounds"] == 1


@pytest.mark.asyncio
async def test_actioner_soft_skips_when_learning_verdict_fail_despite_approved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Learning verdict is the source of truth when approved is stale."""
    from app.agents import actioner as actioner_module

    score = AsyncMock()
    commit = AsyncMock()
    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(actioner_module, "score_loop", score)
    monkeypatch.setattr(actioner_module, "commit_round_memories", commit)

    result = await actioner_module.actioner_agent(
        _state(
            approved=True,
            learning={
                "verdict": "fail",
                "reason": "Operator override: replan",
                "suggested_step": "planner",
                "lessons": {
                    "worked": [],
                    "failed": [],
                    "risks": [],
                    "next_time": [],
                },
            },
        ),
    )

    score.assert_not_awaited()
    commit.assert_not_awaited()
    assert result["loop_score"] == 0
    assert result["refine_from"] == "planner"


@pytest.mark.asyncio
async def test_actioner_reuses_cached_score_after_action_review_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interrupt re-entry must not re-score; use the stashed loop score."""
    from app.agents import actioner as actioner_module
    from agent.memory_review import clear_pending, stash_pending

    clear_pending("test-thread", 0)
    stash_pending(
        "test-thread",
        0,
        [PENDING_MEMORY],
        score=SKILL_PREVIEW_SCORE_THRESHOLD,
        score_rationale="cached score",
    )

    score = AsyncMock()
    extract = AsyncMock()
    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(actioner_module, "score_loop", score)
    monkeypatch.setattr(actioner_module, "extract_memory_candidates", extract)
    monkeypatch.setattr(
        actioner_module,
        "interrupt",
        MagicMock(return_value={"memories": [{**PENDING_MEMORY, "keep": True}]}),
    )
    commit = _stub_commit(monkeypatch, actioner_module)

    result = await actioner_module.actioner_agent(
        _state(human_in_the_loop=True, memory_cursor=0),
    )

    score.assert_not_awaited()
    extract.assert_not_awaited()
    assert result["loop_score"] == SKILL_PREVIEW_SCORE_THRESHOLD
    assert result["skill_preview_ready"] is True
    commit.assert_awaited_once()
    clear_pending("test-thread", 0)


@pytest.mark.asyncio
async def test_actioner_increments_rounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actioner must bump the round counter by one."""
    from app.agents import actioner as actioner_module

    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(return_value=ActionScoreResult(score=85, rationale="strong")),
    )
    monkeypatch.setattr(
        actioner_module,
        "extract_memory_candidates",
        AsyncMock(return_value=[]),
    )
    _stub_commit(monkeypatch, actioner_module)

    result = await actioner_module.actioner_agent(_state(rounds=1))

    assert result["role"] == "actioner"
    assert result["rounds"] == 2
    assert result["loop_score"] == 85
    assert result["skill_preview_ready"] is True


@pytest.mark.asyncio
async def test_actioner_maps_legacy_executor_suggest_to_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy executor suggested_step normalizes to planner on soft-skip."""
    from app.agents import actioner as actioner_module

    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())

    result = await actioner_module.actioner_agent(
        _state(
            approved=False,
            learning={
                "verdict": "fail",
                "reason": "needs more tests",
                "suggested_step": "executor",
                "lessons": {
                    "worked": [],
                    "failed": [],
                    "risks": [],
                    "next_time": [],
                },
            },
        ),
    )

    assert result["refine_from"] == "planner"
    assert result["loop_score"] == 0


@pytest.mark.asyncio
async def test_actioner_defaults_to_finish_when_approved_without_learning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing learning with approved=True defaults refine_from to finish."""
    from app.agents import actioner as actioner_module

    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(return_value=ActionScoreResult(score=40, rationale="no learning")),
    )
    monkeypatch.setattr(
        actioner_module,
        "extract_memory_candidates",
        AsyncMock(return_value=[]),
    )
    _stub_commit(monkeypatch, actioner_module)

    result = await actioner_module.actioner_agent(
        _state(learning=None, approved=True),
    )

    assert result["refine_from"] == "finish"


@pytest.mark.asyncio
async def test_actioner_interrupts_when_score_meets_threshold_and_hitl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """High-scoring HITL loops pause at the actioner for action review."""
    from app.agents import actioner as actioner_module

    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(
            return_value=ActionScoreResult(
                score=SKILL_PREVIEW_SCORE_THRESHOLD,
                rationale="ready",
            ),
        ),
    )
    monkeypatch.setattr(
        actioner_module,
        "extract_memory_candidates",
        AsyncMock(return_value=[]),
    )
    interrupt = MagicMock(side_effect=RuntimeError("paused"))
    monkeypatch.setattr(actioner_module, "interrupt", interrupt)

    with pytest.raises(RuntimeError, match="paused"):
        await actioner_module.actioner_agent(_state(human_in_the_loop=True))

    interrupt.assert_called_once()
    payload = interrupt.call_args.args[0]
    assert payload["kind"] == "action_review"
    assert payload["score"] == SKILL_PREVIEW_SCORE_THRESHOLD
    assert payload["skill_preview_ready"] is True
    assert payload["memories"] == []


@pytest.mark.asyncio
async def test_actioner_interrupts_for_pending_memories_when_hitl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HITL loops pause for memory review even below the skill threshold."""
    from app.agents import actioner as actioner_module

    audit = AsyncMock()
    monkeypatch.setattr(actioner_module, "write_audit_event", audit)
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(return_value=ActionScoreResult(score=65, rationale="memory")),
    )
    monkeypatch.setattr(
        actioner_module,
        "extract_memory_candidates",
        AsyncMock(return_value=[PENDING_MEMORY]),
    )
    interrupt = MagicMock(
        return_value={
            "memories": [
                {
                    **PENDING_MEMORY,
                    "keep": True,
                    "content": "User prefers focused pytest verification.",
                },
            ],
        },
    )
    monkeypatch.setattr(actioner_module, "interrupt", interrupt)
    commit = _stub_commit(monkeypatch, actioner_module)

    result = await actioner_module.actioner_agent(_state(human_in_the_loop=True))

    interrupt.assert_called_once()
    payload = interrupt.call_args.args[0]
    assert payload["kind"] == "action_review"
    assert payload["skill_preview_ready"] is False
    assert payload["memories"] == [PENDING_MEMORY]
    assert result["pending_memories"] == []
    assert result["approved_memories"] == []
    seen_approved = commit.await_args.args[0]["approved_memories"]
    assert seen_approved == [
        {
            "content": "User prefers focused pytest verification.",
            "memory_type": "preference",
            "importance": 0.8,
        },
    ]
    assert audit.await_args.kwargs["payload"]["pending_memory_count"] == 1
    assert audit.await_args.kwargs["payload"]["approved_memory_count"] == 1
    assert audit.await_args.kwargs["payload"]["action_review_interrupted"] is True


@pytest.mark.asyncio
async def test_actioner_reuses_pending_memories_after_interrupt_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actioner must not re-extract memories when re-entered after interrupt."""
    from app.agents import actioner as actioner_module

    audit = AsyncMock()
    extract = AsyncMock(
        side_effect=[
            [PENDING_MEMORY],
            AssertionError("memory extraction should not run on resume"),
        ],
    )
    resume_value = {
        "memories": [
            {
                **PENDING_MEMORY,
                "keep": True,
                "content": "User prefers pytest -v for targeted checks.",
            },
        ],
    }
    interrupt = MagicMock(side_effect=[RuntimeError("paused"), resume_value])

    monkeypatch.setattr(actioner_module, "write_audit_event", audit)
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(return_value=ActionScoreResult(score=65, rationale="memory")),
    )
    monkeypatch.setattr(actioner_module, "extract_memory_candidates", extract)
    monkeypatch.setattr(actioner_module, "interrupt", interrupt)
    commit = _stub_commit(monkeypatch, actioner_module)

    state = _state(human_in_the_loop=True, memory_cursor=7)

    with pytest.raises(RuntimeError, match="paused"):
        await actioner_module.actioner_agent(state)

    result = await actioner_module.actioner_agent(state)

    assert extract.await_count == 1
    assert interrupt.call_count == 2
    assert result["pending_memories"] == []
    assert result["approved_memories"] == []
    seen_approved = commit.await_args.args[0]["approved_memories"]
    assert seen_approved == [
        {
            "content": "User prefers pytest -v for targeted checks.",
            "memory_type": "preference",
            "importance": 0.8,
        },
    ]
    assert audit.await_args.kwargs["payload"]["approved_memory_count"] == 1


@pytest.mark.asyncio
async def test_actioner_merges_learning_candidates_and_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass path merges learner candidates with extract then commits."""
    from app.agents import actioner as actioner_module

    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(return_value=ActionScoreResult(score=70, rationale="ok")),
    )
    monkeypatch.setattr(
        actioner_module,
        "extract_memory_candidates",
        AsyncMock(
            return_value=[
                {
                    "id": "ignore",
                    "content": "Project uses FastAPI",
                    "memory_type": "fact",
                    "importance": 0.6,
                },
            ],
        ),
    )
    commit = _stub_commit(monkeypatch, actioner_module)

    result = await actioner_module.actioner_agent(
        _state(
            learning_candidates=[
                {
                    "id": "old",
                    "content": "User prefers pytest",
                    "memory_type": "preference",
                    "importance": 0.9,
                },
            ],
        ),
    )

    commit.assert_awaited_once()
    pending = commit.await_args.args[0]["pending_memories"]
    assert {row["content"] for row in pending} == {
        "User prefers pytest",
        "Project uses FastAPI",
    }
    assert result["pending_memories"] == []
    assert result["approved_memories"] == []


@pytest.mark.asyncio
async def test_actioner_auto_approves_when_hitl_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-HITL loops approve extracted memories without interrupting."""
    from app.agents import actioner as actioner_module

    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(return_value=ActionScoreResult(score=65, rationale="auto")),
    )
    monkeypatch.setattr(
        actioner_module,
        "extract_memory_candidates",
        AsyncMock(return_value=[PENDING_MEMORY]),
    )
    interrupt = MagicMock()
    monkeypatch.setattr(actioner_module, "interrupt", interrupt)
    commit = _stub_commit(monkeypatch, actioner_module)

    result = await actioner_module.actioner_agent(_state())

    interrupt.assert_not_called()
    assert result["pending_memories"] == []
    assert result["approved_memories"] == []
    assert commit.await_args.args[0]["approved_memories"] == [
        {
            "content": PENDING_MEMORY["content"],
            "memory_type": PENDING_MEMORY["memory_type"],
            "importance": PENDING_MEMORY["importance"],
        },
    ]


@pytest.mark.asyncio
async def test_actioner_skips_interrupt_when_score_below_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Low-scoring loops continue without a HITL pause at the actioner."""
    from app.agents import actioner as actioner_module

    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(return_value=ActionScoreResult(score=65, rationale="refine")),
    )
    monkeypatch.setattr(
        actioner_module,
        "extract_memory_candidates",
        AsyncMock(return_value=[]),
    )
    interrupt = MagicMock()
    monkeypatch.setattr(actioner_module, "interrupt", interrupt)
    _stub_commit(monkeypatch, actioner_module)

    result = await actioner_module.actioner_agent(_state(human_in_the_loop=True))

    interrupt.assert_not_called()
    assert result["skill_preview_ready"] is False
    assert result["pending_memories"] == []
    assert result["approved_memories"] == []


@pytest.mark.asyncio
async def test_actioner_writes_audit_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actioner must audit the routing decision and score."""
    from app.agents import actioner as actioner_module

    audit = AsyncMock()
    monkeypatch.setattr(actioner_module, "write_audit_event", audit)
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(return_value=ActionScoreResult(score=90, rationale="excellent")),
    )
    monkeypatch.setattr(
        actioner_module,
        "extract_memory_candidates",
        AsyncMock(return_value=[]),
    )
    _stub_commit(monkeypatch, actioner_module)

    await actioner_module.actioner_agent(
        _state(
            rounds=2,
            approved=True,
        ),
    )

    audit.assert_awaited_once()
    kwargs = audit.await_args.kwargs
    assert kwargs["thread_id"] == "test-thread"
    assert kwargs["round_number"] == 3
    assert kwargs["node"] == "actioner"
    assert kwargs["event_type"] == "route_decision"
    assert kwargs["payload"]["suggested_step"] == "finish"
    assert kwargs["payload"]["approved"] is True
    assert kwargs["payload"]["loop_score"] == 90
    assert kwargs["payload"]["skill_preview_ready"] is True
    assert kwargs["payload"]["score_rationale"] == "excellent"
    assert kwargs["payload"]["pending_memory_count"] == 0
    assert kwargs["payload"]["approved_memory_count"] == 0
    assert kwargs["payload"]["action_review_interrupted"] is False
    assert kwargs["payload"]["soft_skip"] is False


def test_merge_learning_and_extract_dedupes_by_content() -> None:
    """Merge assigns m0.. ids and drops duplicate normalized content."""
    from agent.actioner import merge_learning_and_extract

    merged = merge_learning_and_extract(
        [
            {
                "id": "a",
                "content": " Prefer Pytest ",
                "memory_type": "preference",
                "importance": 0.9,
            },
        ],
        [
            {
                "id": "b",
                "content": "prefer pytest",
                "memory_type": "fact",
                "importance": 0.2,
            },
            {
                "id": "c",
                "content": "Uses FastAPI",
                "memory_type": "fact",
                "importance": 0.5,
            },
        ],
    )
    assert len(merged) == 2
    assert merged[0]["id"] == "m0"
    assert merged[0]["content"] == "Prefer Pytest"
    assert merged[1]["id"] == "m1"
    assert merged[1]["content"] == "Uses FastAPI"
