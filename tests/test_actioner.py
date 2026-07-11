"""Tests for the actioner agent node."""

from __future__ import annotations

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
        "approved": False,
        "human_in_the_loop": False,
        "review": {
            "verdict": "pass",
            "reason": "looks good",
            "suggested_step": "finish",
        },
        "execution": {
            "summary": "implemented feature",
            "changes": ["added tests"],
            "risks": [],
            "verification": ["pytest passes"],
        },
    }
    base.update(overrides)
    return base


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

    result = await actioner_module.actioner_agent(_state(rounds=1))

    assert result["role"] == "actioner"
    assert result["rounds"] == 2
    assert result["loop_score"] == 85
    assert result["skill_preview_ready"] is True


@pytest.mark.asyncio
async def test_actioner_sets_refine_from_from_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actioner copies the reviewer's suggested_step into refine_from."""
    from app.agents import actioner as actioner_module

    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(return_value=ActionScoreResult(score=55, rationale="needs work")),
    )
    monkeypatch.setattr(
        actioner_module,
        "extract_memory_candidates",
        AsyncMock(return_value=[]),
    )

    result = await actioner_module.actioner_agent(
        _state(
            review={
                "verdict": "fail",
                "reason": "needs more tests",
                "suggested_step": "executor",
            },
        ),
    )

    assert result["refine_from"] == "executor"
    assert result["skill_preview_ready"] is False


@pytest.mark.asyncio
async def test_actioner_defaults_to_finish_when_no_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing review should default refine_from to finish."""
    from app.agents import actioner as actioner_module

    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(return_value=ActionScoreResult(score=0, rationale="no review")),
    )
    monkeypatch.setattr(
        actioner_module,
        "extract_memory_candidates",
        AsyncMock(return_value=[]),
    )

    result = await actioner_module.actioner_agent(_state(review=None))

    assert result["refine_from"] == "finish"
    assert result["skill_preview_ready"] is False


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

    result = await actioner_module.actioner_agent(_state(human_in_the_loop=True))

    interrupt.assert_called_once()
    payload = interrupt.call_args.args[0]
    assert payload["kind"] == "action_review"
    assert payload["skill_preview_ready"] is False
    assert payload["memories"] == [PENDING_MEMORY]
    assert result["pending_memories"] == [PENDING_MEMORY]
    assert result["approved_memories"] == [
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

    result = await actioner_module.actioner_agent(_state())

    interrupt.assert_not_called()
    assert result["pending_memories"] == [PENDING_MEMORY]
    assert result["approved_memories"] == [
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
    assert kwargs["payload"]["pending_memory_count"] == 0
    assert kwargs["payload"]["approved_memory_count"] == 0
    assert kwargs["payload"]["action_review_interrupted"] is False


def test_heuristic_loop_score_pass_verdict_scores_high() -> None:
    """Heuristic scoring should reach the preview threshold on strong loops."""
    from app.agents import actioner as actioner_module

    score = actioner_module._heuristic_loop_score(_state())
    assert score >= SKILL_PREVIEW_SCORE_THRESHOLD


def test_heuristic_loop_score_without_review_is_zero() -> None:
    """Missing review should score zero."""
    from app.agents import actioner as actioner_module

    assert actioner_module._heuristic_loop_score(_state(review=None)) == 0
