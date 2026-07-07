"""Tests for the actioner agent node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from graph.schemas import ActionScoreResult
from skills.eligibility import SKILL_PREVIEW_SCORE_THRESHOLD


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

    result = await actioner_module.actioner_agent(_state(review=None))

    assert result["refine_from"] == "finish"
    assert result["skill_preview_ready"] is False


@pytest.mark.asyncio
async def test_actioner_interrupts_when_score_meets_threshold_and_hitl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """High-scoring HITL loops pause at the actioner for skill preview."""
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
    interrupt = MagicMock(side_effect=RuntimeError("paused"))
    monkeypatch.setattr(actioner_module, "interrupt", interrupt)

    with pytest.raises(RuntimeError, match="paused"):
        await actioner_module.actioner_agent(_state(human_in_the_loop=True))

    interrupt.assert_called_once()
    payload = interrupt.call_args.args[0]
    assert payload["kind"] == "skill_preview"
    assert payload["score"] == SKILL_PREVIEW_SCORE_THRESHOLD


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
    interrupt = MagicMock()
    monkeypatch.setattr(actioner_module, "interrupt", interrupt)

    result = await actioner_module.actioner_agent(_state(human_in_the_loop=True))

    interrupt.assert_not_called()
    assert result["skill_preview_ready"] is False


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


def test_heuristic_loop_score_pass_verdict_scores_high() -> None:
    """Heuristic scoring should reach the preview threshold on strong loops."""
    from app.agents import actioner as actioner_module

    score = actioner_module._heuristic_loop_score(_state())
    assert score >= SKILL_PREVIEW_SCORE_THRESHOLD


def test_heuristic_loop_score_without_review_is_zero() -> None:
    """Missing review should score zero."""
    from app.agents import actioner as actioner_module

    assert actioner_module._heuristic_loop_score(_state(review=None)) == 0
