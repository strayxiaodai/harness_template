"""Tests for user task rewrite prompt, agent, and planner integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agent.planner import planner_agent
from agent.task_rewrite import (
    format_task_rewrite_input,
    is_task_rewrite_enabled,
    rewrite_task_input,
)
from app.schemas.run import RunRequest
from app.services.state import initial_state
from graph.schemas import PlanResult


def test_is_task_rewrite_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # State override takes priority
    assert is_task_rewrite_enabled({"rewrite_task": True}) is True
    assert is_task_rewrite_enabled({"rewrite_task": False}) is False

    # Falls back to environment variable
    monkeypatch.setenv("TASK_REWRITE_ENABLED", "true")
    assert is_task_rewrite_enabled({}) is True
    assert is_task_rewrite_enabled(None) is True

    monkeypatch.setenv("TASK_REWRITE_ENABLED", "false")
    assert is_task_rewrite_enabled({}) is False
    assert is_task_rewrite_enabled(None) is False


def test_format_task_rewrite_input() -> None:
    formatted = format_task_rewrite_input("optimize memory cache")
    assert "Raw User Task:\noptimize memory cache" in formatted
    assert "Recent Conversation Messages:" not in formatted

    messages = [
        HumanMessage(content="Hello"),
        AIMessage(content="How can I help?"),
    ]
    formatted_with_msgs = format_task_rewrite_input("make it faster", messages)
    assert "Raw User Task:\nmake it faster" in formatted_with_msgs
    assert "Recent Conversation Messages:" in formatted_with_msgs
    assert "[human]: Hello" in formatted_with_msgs
    assert "[ai]: How can I help?" in formatted_with_msgs


@pytest.mark.asyncio
async def test_rewrite_task_input_with_test_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "test")
    res = await rewrite_task_input("short user task")
    assert isinstance(res, str)
    assert len(res) > 0


@pytest.mark.asyncio
async def test_rewrite_task_input_empty_fallback() -> None:
    assert await rewrite_task_input("") == ""
    assert await rewrite_task_input("   ") == "   "


def test_initial_state_sets_rewrite_task_flag() -> None:
    req = RunRequest(
        task="build auth",
        thread_id="test-thread",
        rewrite_task=True,
    )
    state = initial_state(req)
    assert state.get("rewrite_task") is True

    req_default = RunRequest(
        task="build auth",
        thread_id="test-thread",
    )
    state_default = initial_state(req_default)
    assert "rewrite_task" not in state_default


@pytest.mark.asyncio
async def test_planner_rewrites_task_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_plan = PlanResult(
        steps=["Step 1: Check repo", "Step 2: Implement"],
        rationale="Clear plan based on structured specification",
    )
    monkeypatch.setattr(
        "agent.planner.call_llm",
        AsyncMock(return_value=mock_plan),
    )

    rewritten_spec = (
        "# Role\nYou are a Senior Backend Engineer.\n"
        "# Core Objectives\n1. Implement Redis caching."
    )
    monkeypatch.setattr(
        "agent.planner.rewrite_task_input",
        AsyncMock(return_value=rewritten_spec),
    )

    state = {
        "thread_id": "t-1",
        "task": "add redis caching",
        "messages": [],
        "plan": [],
        "rounds": 0,
        "max_rounds": 3,
        "role": "",
        "approved": False,
        "human_in_the_loop": False,
        "rewrite_task": True,
    }

    result = await planner_agent(state)
    assert result["task"] == rewritten_spec
    assert result["raw_task"] == "add redis caching"
    assert result["task_rewritten"] is True
    assert result["plan"] == ["Step 1: Check repo", "Step 2: Implement"]


@pytest.mark.asyncio
async def test_planner_skips_rewrite_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_plan = PlanResult(
        steps=["Step 1: Do something"],
        rationale="Simple rationale",
    )
    monkeypatch.setattr(
        "agent.planner.call_llm",
        AsyncMock(return_value=mock_plan),
    )
    mock_rewrite = AsyncMock()
    monkeypatch.setattr("agent.planner.rewrite_task_input", mock_rewrite)

    state = {
        "thread_id": "t-2",
        "task": "raw task unchanged",
        "messages": [],
        "plan": [],
        "rounds": 0,
        "max_rounds": 3,
        "role": "",
        "approved": False,
        "human_in_the_loop": False,
        "rewrite_task": False,
    }

    result = await planner_agent(state)
    mock_rewrite.assert_not_awaited()
    assert "raw_task" not in result
    assert "task_rewritten" not in result
    assert "task" not in result

