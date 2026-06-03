"""Tests for the executor agent node."""

from __future__ import annotations

import os, logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.graph.schemas import ExecutorResult

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
    """Build a minimal AgentState dict for executor tests."""
    base: dict[str, Any] = {
        "thread_id": "test-thread",
        "task": "Implement feature",
        "messages": [],
        "plan": ["step one", "step two"],
        "rounds": 0,
        "max_rounds": 3,
        "role": "executor",
        "approved": False,
        "human_in_the_loop": False,
    }
    base.update(overrides)
    return base


def _patch_llm_and_tools(
    monkeypatch: pytest.MonkeyPatch,
    executor_module: Any,
) -> MagicMock:
    """Patch get_llm and get_executor_tools; return the fake LLM."""
    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = MagicMock(name="bound_llm")
    fake_llm.with_structured_output.return_value = MagicMock(name="structured")
    monkeypatch.setattr(executor_module, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(
        executor_module,
        "get_executor_tools",
        lambda: [MagicMock(name="tool")],
    )
    return fake_llm


def _tool_call(name: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    """Build an AIMessage tool_call dict."""
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


@pytest.mark.asyncio
async def test_executor_returns_structured_result_without_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the model requests no tools, the summary phase still runs."""
    from app.agents import executor as executor_module

    fake_llm = _patch_llm_and_tools(monkeypatch, executor_module)
    audit = AsyncMock()
    monkeypatch.setattr(executor_module, "write_audit_event", audit)

    response = AIMessage(content="nothing to do")
    execution = ExecutorResult(
        summary="all done",
        changes=["edited file"],
        risks=[],
        verification=["ran tests"],
    )
    monkeypatch.setattr(
        executor_module,
        "call_llm",
        AsyncMock(side_effect=[response, execution]),
    )

    result = await executor_module.executor_agent(_state())

    assert result["role"] == "executor"
    assert result["result"] == "all done"
    assert result["execution"] == execution.model_dump()
    assert result["tool_calls"] == []
    assert any(
        "Executor summary: all done" in m.content for m in result["messages"]
    )
    assert executor_module.call_llm.await_count == 2
    fake_llm.with_structured_output.assert_called_once_with(ExecutorResult)
    audit.assert_not_awaited()


@pytest.mark.asyncio
async def test_executor_runs_tool_and_records_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A requested tool runs once and is recorded and audited."""
    from app.agents import executor as executor_module

    _patch_llm_and_tools(monkeypatch, executor_module)
    audit = AsyncMock()
    monkeypatch.setattr(executor_module, "write_audit_event", audit)

    fake_tool = MagicMock()
    fake_tool.ainvoke = AsyncMock(return_value="file contents")
    monkeypatch.setattr(
        executor_module,
        "get_tool_by_name",
        lambda name: fake_tool,
    )

    response = AIMessage(
        content="",
        tool_calls=[_tool_call("read_file", {"path": "README.md"}, "call_1")],
    )
    follow_up = AIMessage(content="done reading")
    execution = ExecutorResult(summary="read the file")
    monkeypatch.setattr(
        executor_module,
        "call_llm",
        AsyncMock(side_effect=[response, follow_up, execution]),
    )

    result = await executor_module.executor_agent(_state())

    assert len(result["tool_calls"]) == 1
    record = result["tool_calls"][0]
    assert record["tool"] == "read_file"
    assert record["args"] == {"path": "README.md"}
    assert record["status"] == "ok"
    assert record["iteration"] == 0
    fake_tool.ainvoke.assert_awaited_once_with({"path": "README.md"})

    tool_messages = [
        m for m in result["messages"] if isinstance(m, ToolMessage)
    ]
    assert len(tool_messages) == 1
    assert tool_messages[0].content == "file contents"
    assert tool_messages[0].tool_call_id == "call_1"

    audit.assert_awaited_once()
    audit_kwargs = audit.await_args.kwargs
    assert audit_kwargs["event_type"] == "tool_call"
    assert audit_kwargs["node"] == "executor"
    assert audit_kwargs["round_number"] == 1
    assert audit_kwargs["payload"]["tool"] == "read_file"
    assert audit_kwargs["payload"]["status"] == "ok"


@pytest.mark.asyncio
async def test_executor_records_tool_error_without_aborting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing tool is recorded as error; the summary phase still runs."""
    from app.agents import executor as executor_module

    _patch_llm_and_tools(monkeypatch, executor_module)
    monkeypatch.setattr(executor_module, "write_audit_event", AsyncMock())

    fake_tool = MagicMock()
    fake_tool.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(
        executor_module,
        "get_tool_by_name",
        lambda name: fake_tool,
    )

    response = AIMessage(
        content="",
        tool_calls=[_tool_call("read_file", {"path": "x"}, "call_1")],
    )
    follow_up = AIMessage(content="done")
    execution = ExecutorResult(summary="handled the error")
    monkeypatch.setattr(
        executor_module,
        "call_llm",
        AsyncMock(side_effect=[response, follow_up, execution]),
    )

    result = await executor_module.executor_agent(_state())

    record = result["tool_calls"][0]
    assert record["status"] == "error"

    tool_messages = [
        m for m in result["messages"] if isinstance(m, ToolMessage)
    ]
    assert "boom" in tool_messages[0].content
    assert result["result"] == "handled the error"


@pytest.mark.asyncio
async def test_executor_includes_review_feedback_in_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Executor must pass prior review reason, task, and plan into the prompt."""
    from app.agents import executor as executor_module

    _patch_llm_and_tools(monkeypatch, executor_module)
    monkeypatch.setattr(executor_module, "write_audit_event", AsyncMock())

    captured_messages: list[Any] = []
    execution = ExecutorResult(summary="done")
    phase = {"count": 0}

    async def fake_call_llm(runnable: Any, messages: list[Any]) -> Any:
        del runnable
        if phase["count"] == 0:
            captured_messages.extend(messages)
            phase["count"] += 1
            return AIMessage(content="no tools needed")
        return execution

    monkeypatch.setattr(executor_module, "call_llm", fake_call_llm)

    await executor_module.executor_agent(
        _state(
            review={
                "verdict": "fail",
                "reason": "missing tests",
                "suggested_step": "executor",
            },
        ),
    )

    human_messages = [
        m for m in captured_messages if isinstance(m, HumanMessage)
    ]
    assert len(human_messages) == 1
    assert "missing tests" in human_messages[0].content
    assert "Implement feature" in human_messages[0].content
    assert "step one" in human_messages[0].content


@pytest.mark.asyncio
@pytest.mark.integration
async def test_executor_produces_summary_live() -> None:
    """Live smoke: run the planner, then execute its plan end-to-end."""
    if not _llm_credentials_configured():
        pytest.skip("LLM credentials not configured for live executor test")

    from app.agents import executor as executor_module
    from app.agents import planner as planner_module

    task = "Write an interview plan for a new AI engineer role"

    plan_result = await planner_module.planner_agent(_state(task=task, plan=[]))
    plan = plan_result["plan"]
    assert plan, "planner returned an empty plan"
    logger.info("\nPlanner generated:\n%s", "\n".join(plan))
    result = await executor_module.executor_agent(
        _state(task=task, plan=plan),
    )

    assert result["role"] == "executor"
    assert isinstance(result["result"], str) and result["result"].strip()
    logger.info("\n\nExecutor generated:\n%s", result["result"])
    assert result["execution"]["summary"].strip()
