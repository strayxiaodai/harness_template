"""Tests for the reviewer agent node."""

from __future__ import annotations

import logging
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import HumanMessage

from app.graph.schemas import ReviewResult

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
    """Build a minimal AgentState dict for reviewer tests."""
    base: dict[str, Any] = {
        "thread_id": "test-thread",
        "task": "Implement feature",
        "messages": [],
        "plan": ["step one", "step two"],
        "rounds": 0,
        "max_rounds": 3,
        "role": "reviewer",
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
async def test_reviewer_writes_review_to_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reviewer must return structured review and role reviewer."""
    from app.agents import reviewer as reviewer_module

    review = ReviewResult(
        verdict="fail",
        reason="missing edge-case tests",
        suggested_step="executor",
    )
    fake_structured = MagicMock()
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    monkeypatch.setattr(reviewer_module, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(
        reviewer_module,
        "call_llm",
        AsyncMock(return_value=review),
    )

    result = await reviewer_module.reviewer_agent(_state())

    assert result["role"] == "reviewer"
    assert result["approved"] is False
    assert result["review"] == review.model_dump()
    assert len(result["messages"]) == 1
    assert "missing edge-case tests" in result["messages"][0].content
    fake_llm.with_structured_output.assert_called_once_with(ReviewResult)


@pytest.mark.asyncio
async def test_reviewer_sets_approved_on_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pass verdict must set approved=True."""
    from app.agents import reviewer as reviewer_module

    review = ReviewResult(
        verdict="pass",
        reason="looks good",
        suggested_step="finish",
    )
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = MagicMock()
    monkeypatch.setattr(reviewer_module, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(
        reviewer_module,
        "call_llm",
        AsyncMock(return_value=review),
    )

    result = await reviewer_module.reviewer_agent(_state())

    assert result["approved"] is True
    assert result["review"]["verdict"] == "pass"
    assert result["review"]["suggested_step"] == "finish"


@pytest.mark.asyncio
async def test_reviewer_includes_execution_and_tool_calls_in_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reviewer must pass execution details and tool calls into the prompt."""
    from app.agents import reviewer as reviewer_module

    captured_messages: list[Any] = []
    review = ReviewResult(
        verdict="fail",
        reason="ignored tool output",
        suggested_step="executor",
    )

    async def fake_call_llm(
        runnable: Any,
        messages: list[Any],
    ) -> ReviewResult:
        del runnable
        captured_messages.extend(messages)
        return review

    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = MagicMock()
    monkeypatch.setattr(reviewer_module, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(reviewer_module, "call_llm", fake_call_llm)

    await reviewer_module.reviewer_agent(
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
    assert len(human_messages) == 1
    content = human_messages[0].content
    assert "implemented the feature" in content
    assert "edited main.py" in content
    assert "read_file" in content
    assert "Implement feature" in content
    assert "step one" in content


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reviewer_returns_structured_verdict_live() -> None:
    """Live smoke: reviewer returns a structured verdict for executor output."""
    if not _llm_credentials_configured():
        pytest.skip("LLM credentials not configured for live reviewer test")

    from app.agents import reviewer as reviewer_module

    result = await reviewer_module.reviewer_agent(_state())

    assert result["role"] == "reviewer"
    assert result["review"]["verdict"] in {"pass", "fail"}
    assert result["review"]["reason"].strip()
    assert result["review"]["suggested_step"] in {
        "planner",
        "executor",
        "finish",
    }
    assert result["approved"] == (result["review"]["verdict"] == "pass")
    logger.info(
        "\n\nReviewer verdict: %s — %s (next: %s)",
        result["review"]["verdict"],
        result["review"]["reason"],
        result["review"]["suggested_step"],
    )
