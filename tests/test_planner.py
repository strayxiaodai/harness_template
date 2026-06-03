"""Tests for the planner agent node."""

from __future__ import annotations
import logging

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import HumanMessage

from app.graph.schemas import PlanResult

logger = logging.getLogger(__name__)

def _llm_credentials_configured() -> bool:
    """Return True when the configured provider has credentials."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    if provider == "ollama":
        return True
    return False


def _state(**overrides: object) -> dict[str, Any]:
    """Build a minimal AgentState dict for planner tests."""
    base: dict[str, Any] = {
        "thread_id": "test-thread",
        "task": "Implement feature",
        "messages": [],
        "plan": ["existing step"],
        "rounds": 0,
        "max_rounds": 3,
        "role": "planner",
        "approved": False,
        "human_in_the_loop": False,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_planner_writes_plan_to_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Planner must return structured steps as state.plan and role planner."""
    from app.agents import planner as planner_module

    plan = PlanResult(steps=["a", "b"], rationale="why")
    fake_structured = MagicMock()
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    monkeypatch.setattr(planner_module, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(
        planner_module,
        "call_llm",
        AsyncMock(return_value=plan),
    )

    result = await planner_module.planner_agent(_state())

    assert result["plan"] == ["a", "b"]
    assert result["role"] == "planner"
    assert len(result["messages"]) == 1
    assert "why" in result["messages"][0].content
    fake_llm.with_structured_output.assert_called_once_with(PlanResult)
    planner_module.call_llm.assert_awaited_once()
    await_args = planner_module.call_llm.await_args
    assert await_args is not None
    assert await_args.args[0] is fake_structured


@pytest.mark.asyncio
async def test_planner_includes_review_feedback_in_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Planner must pass prior review reason into the human message."""
    from app.agents import planner as planner_module

    plan = PlanResult(steps=["revise"], rationale="updated")
    captured_messages: list[Any] = []

    async def fake_call_llm(
        runnable: Any,
        messages: list[Any],
    ) -> PlanResult:
        del runnable
        captured_messages.extend(messages)
        return plan

    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = MagicMock()
    monkeypatch.setattr(planner_module, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(planner_module, "call_llm", fake_call_llm)

    await planner_module.planner_agent(
        _state(
            review={
                "verdict": "fail",
                "reason": "missing tests",
                "suggested_step": "planner",
            },
        ),
    )

    human_messages = [
        m for m in captured_messages if isinstance(m, HumanMessage)
    ]
    assert len(human_messages) == 1
    assert "missing tests" in human_messages[0].content
    assert "Implement feature" in human_messages[0].content


@pytest.mark.asyncio
@pytest.mark.integration
async def test_planner_generates_interview_plan_live() -> None:
    """Live smoke: planner returns a non-empty structured plan for a task."""
    if not _llm_credentials_configured():
        pytest.skip("LLM credentials not configured for live planner test")

    from app.agents import planner as planner_module

    result = await planner_module.planner_agent(
        {
            "thread_id": "smoke",
            "task": (
                "Write an interview plan for a new AI engineer role"
            ),
            "messages": [],
            "plan": [],
            "rounds": 0,
            "max_rounds": 3,
            "role": "planner",
            "approved": False,
            "human_in_the_loop": False,
        },
    )

    assert result["role"] == "planner"
    assert result["plan"]
    logger.info("\n\nPlanner steps:\n%s", "\n".join(result["plan"]))
    assert all(isinstance(step, str) and step.strip() for step in result["plan"])
    assert len(result["messages"]) == 1
    assert "Plan rationale:" in result["messages"][0].content
