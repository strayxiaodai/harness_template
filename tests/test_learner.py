"""Tests for the learner agent node."""

from __future__ import annotations

import logging
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from graph.schemas import LearningResult, LessonsBlock

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
    """Build a minimal AgentState dict for learner tests."""
    base: dict[str, Any] = {
        "thread_id": "test-thread",
        "task": "Implement feature",
        "messages": [],
        "plan": ["step one", "step two"],
        "rounds": 0,
        "max_rounds": 3,
        "role": "learner",
        "approved": False,
        "human_in_the_loop": False,
        "execution": {
            "summary": "implemented the feature",
            "changes": ["edited main.py"],
            "risks": ["none noted"],
            "verification": ["ran unit tests"],
        },
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_learner_writes_learning_to_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Learner must return structured learning and role learner."""
    from app.agents import learner as learner_module

    learning = LearningResult(
        verdict="fail",
        reason="missing edge-case tests",
        suggested_step="planner",
        lessons=LessonsBlock(
            worked=[],
            failed=["no edge-case coverage"],
            risks=[],
            next_time=["add tests"],
        ),
        learning_candidates=[],
    )
    fake_structured = MagicMock()
    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    monkeypatch.setattr(learner_module, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(
        learner_module,
        "get_learner_tools",
        lambda _tid: [],
    )
    monkeypatch.setattr(learner_module, "lookup_thread_dir", lambda _tid: None)
    monkeypatch.setattr(
        learner_module,
        "call_llm",
        AsyncMock(side_effect=[AIMessage(content="reviewed"), learning]),
    )

    result = await learner_module.learner_agent(_state())

    assert result["role"] == "learner"
    assert result["approved"] is False
    assert result["learning"]["verdict"] == "fail"
    assert result["learning"]["lessons"]["failed"] == ["no edge-case coverage"]
    assert result["learning_candidates"] == []
    assert "review" not in result
    assert result["learner_tool_calls"] == []
    assert any("missing edge-case tests" in m.content for m in result["messages"])
    fake_llm.with_structured_output.assert_called_once_with(LearningResult)


@pytest.mark.asyncio
async def test_learner_sets_approved_on_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pass verdict must set approved=True and may include candidates."""
    from app.agents import learner as learner_module

    learning = LearningResult(
        verdict="pass",
        reason="looks good",
        suggested_step="finish",
        lessons=LessonsBlock(worked=["verification ran"]),
        learning_candidates=[
            {
                "id": "m0",
                "content": "Prefer unit tests before finish",
                "memory_type": "preference",
                "importance": 0.7,
            },
        ],
    )
    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = MagicMock()
    fake_llm.with_structured_output.return_value = MagicMock()
    monkeypatch.setattr(learner_module, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(
        learner_module,
        "get_learner_tools",
        lambda _tid: [],
    )
    monkeypatch.setattr(learner_module, "lookup_thread_dir", lambda _tid: None)
    monkeypatch.setattr(
        learner_module,
        "call_llm",
        AsyncMock(side_effect=[AIMessage(content="ok"), learning]),
    )

    result = await learner_module.learner_agent(_state())

    assert result["approved"] is True
    assert result["learning"]["verdict"] == "pass"
    assert result["learning"]["suggested_step"] == "finish"
    assert result["learning_candidates"][0]["id"] == "m0"


@pytest.mark.asyncio
async def test_learner_includes_execution_and_tool_calls_in_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Learner must pass execution details and tool calls into the prompt."""
    from app.agents import learner as learner_module

    captured_messages: list[Any] = []
    learning = LearningResult(
        verdict="fail",
        reason="ignored tool output",
        suggested_step="planner",
        lessons=LessonsBlock(),
        learning_candidates=[],
    )

    call_count = {"n": 0}

    async def fake_call_llm(
        runnable: Any,
        messages: list[Any],
    ) -> Any:
        del runnable
        captured_messages.extend(messages)
        call_count["n"] += 1
        if call_count["n"] == 1:
            return AIMessage(content="no tools needed")
        return learning

    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = MagicMock()
    fake_llm.with_structured_output.return_value = MagicMock()
    monkeypatch.setattr(learner_module, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(
        learner_module,
        "get_learner_tools",
        lambda _tid: [],
    )
    monkeypatch.setattr(learner_module, "lookup_thread_dir", lambda _tid: None)
    monkeypatch.setattr(learner_module, "call_llm", fake_call_llm)

    await learner_module.learner_agent(
        _state(
            tool_calls=[
                {
                    "iteration": 0,
                    "tool": "read_file",
                    "args": {"path": "main.py"},
                    "status": "ok",
                },
            ],
        ),
    )

    human_messages = [
        message for message in captured_messages if isinstance(message, HumanMessage)
    ]
    assert len(human_messages) >= 1
    content = human_messages[0].content
    assert "implemented the feature" in content
    assert "edited main.py" in content
    assert "read_file" in content
    assert "Implement feature" in content
    assert "step one" in content


@pytest.mark.asyncio
@pytest.mark.integration
async def test_learner_returns_structured_verdict_live() -> None:
    """Live smoke: learner returns structured learning for executor output."""
    if not _llm_credentials_configured():
        pytest.skip("LLM credentials not configured for live learner test")

    from app.agents import learner as learner_module

    result = await learner_module.learner_agent(_state())

    assert result["role"] == "learner"
    assert result["learning"]["verdict"] in {"pass", "fail"}
    assert result["learning"]["reason"].strip()
    assert result["learning"]["suggested_step"] in {"planner", "finish"}
    assert "lessons" in result["learning"]
    assert isinstance(result["learning_candidates"], list)
    assert result["approved"] == (result["learning"]["verdict"] == "pass")
    logger.info(
        "\n\nLearner verdict: %s — %s (next: %s)",
        result["learning"]["verdict"],
        result["learning"]["reason"],
        result["learning"]["suggested_step"],
    )
