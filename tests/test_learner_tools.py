# tests/test_learner_tools.py
"""Tests for learner tool-calling loop."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from graph.schemas import LearningResult, LessonsBlock


def _state(**overrides: object) -> dict[str, Any]:
    """Minimal learner state."""
    base: dict[str, Any] = {
        "thread_id": "test-thread",
        "task": "Implement feature",
        "messages": [],
        "plan": ["step one"],
        "rounds": 0,
        "max_rounds": 3,
        "role": "learner",
        "approved": False,
        "human_in_the_loop": False,
        "execution": {
            "summary": "done",
            "changes": [],
            "risks": [],
            "verification": [],
        },
    }
    base.update(overrides)
    return base


def _tool_call(name: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


@pytest.mark.asyncio
async def test_learner_runs_tool_then_summarizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Learner tool loop records run_thread_script then returns LearningResult."""
    from app.agents import learner as learner_module

    learning = LearningResult(
        verdict="pass",
        reason="script verified",
        suggested_step="finish",
        lessons=LessonsBlock(worked=["ran script"], failed=[], risks=[], next_time=[]),
        learning_candidates=[],
    )

    fake_tool = MagicMock()
    fake_tool.name = "run_thread_script"
    fake_tool.ainvoke = AsyncMock(
        return_value='{"status":"ok","exit_code":0,"stdout":"ok"}'
    )

    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = MagicMock(name="bound")
    fake_llm.with_structured_output.return_value = MagicMock(name="structured")
    monkeypatch.setattr(learner_module, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(
        learner_module,
        "get_learner_tools",
        lambda _tid: [fake_tool],
    )
    monkeypatch.setattr(learner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(learner_module, "lookup_thread_dir", lambda _tid: None)

    response = AIMessage(
        content="",
        tool_calls=[_tool_call("run_thread_script", {"path": "ok.py"}, "c1")],
    )
    follow_up = AIMessage(content="enough evidence")
    monkeypatch.setattr(
        learner_module,
        "call_llm",
        AsyncMock(side_effect=[response, follow_up, learning]),
    )

    result = await learner_module.learner_agent(_state())

    assert len(result["learner_tool_calls"]) == 1
    assert result["learner_tool_calls"][0]["tool"] == "run_thread_script"
    assert result["learner_tool_calls"][0]["status"] == "ok"
    assert result["learning"]["verdict"] == "pass"
    assert any(isinstance(m, ToolMessage) for m in result["messages"])
    fake_tool.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_learner_summarize_phase_excludes_tool_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Structured LearningResult call must not reuse live tool-call history."""
    from app.agents import learner as learner_module
    from langchain_core.messages import HumanMessage

    learning = LearningResult(
        verdict="pass",
        reason="script verified",
        suggested_step="finish",
        lessons=LessonsBlock(worked=["ran script"], failed=[], risks=[], next_time=[]),
        learning_candidates=[],
    )

    fake_tool = MagicMock()
    fake_tool.name = "run_thread_script"
    fake_tool.ainvoke = AsyncMock(
        return_value='{"status":"ok","exit_code":0,"stdout":"ok"}'
    )

    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = MagicMock(name="bound")
    fake_llm.with_structured_output.return_value = MagicMock(name="structured")
    monkeypatch.setattr(learner_module, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(
        learner_module,
        "get_learner_tools",
        lambda _tid: [fake_tool],
    )
    monkeypatch.setattr(learner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(learner_module, "lookup_thread_dir", lambda _tid: None)

    summarize_messages: list[Any] = []
    response = AIMessage(
        content="",
        tool_calls=[_tool_call("run_thread_script", {"path": "ok.py"}, "c1")],
    )
    follow_up = AIMessage(content="enough evidence")
    phase = {"count": 0}

    async def fake_call_llm(runnable: Any, messages: list[Any]) -> Any:
        del runnable
        phase["count"] += 1
        if phase["count"] == 1:
            return response
        if phase["count"] == 2:
            return follow_up
        summarize_messages.extend(messages)
        return learning

    monkeypatch.setattr(learner_module, "call_llm", fake_call_llm)

    await learner_module.learner_agent(_state())

    assert summarize_messages
    assert not any(isinstance(m, ToolMessage) for m in summarize_messages)
    assert not any(
        isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
        for m in summarize_messages
    )
    joined = " ".join(
        m.content for m in summarize_messages if isinstance(m, HumanMessage)
    )
    assert "run_thread_script" in joined
    assert "ok.py" in joined