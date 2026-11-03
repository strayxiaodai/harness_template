"""Unit tests for Pydantic AI Executor Agent and type-safe tool dependency injection."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.models.test import TestModel

from agent.executor import ExecutorDeps, create_executor_agent, executor_agent
from graph.schemas import ExecutorResult


@pytest.mark.asyncio
async def test_create_executor_agent_registers_type_safe_tools() -> None:
    """Agent registers read_file, list_dir, read_thread_file, write_thread_file via @agent.tool."""
    model = TestModel()
    agent = create_executor_agent(model=model)
    tool_names = set(agent._function_toolset.tools.keys())
    assert {"read_file", "list_dir", "read_thread_file", "write_thread_file"}.issubset(tool_names)


@pytest.mark.asyncio
async def test_executor_tools_dependency_injection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tools receive RunContext[ExecutorDeps], record tool calls, and emit audit events."""
    audit_mock = AsyncMock()
    monkeypatch.setattr("agent.executor.write_audit_event", audit_mock)
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(tmp_path))

    # Create dummy workspace file
    workspace_file = Path.cwd() / "a"
    workspace_file.write_text("workspace content", encoding="utf-8")

    try:
        model = TestModel(call_tools=["read_file", "list_dir"])
        agent = create_executor_agent(model=model)
        deps = ExecutorDeps(thread_id="test-deps-thread", round_number=1, workspace_dir=Path.cwd())

        res = await agent.run("execute task", deps=deps)
        assert isinstance(res.output, ExecutorResult)

        # Verify dependency injection populated tool_calls in deps
        assert len(deps.tool_calls) >= 2
        tool_names = [call["tool"] for call in deps.tool_calls]
        assert "read_file" in tool_names
        assert "list_dir" in tool_names

        # Verify audit events were emitted with injected thread_id and round_number
        assert audit_mock.await_count >= 2
        for call_args in audit_mock.await_args_list:
            assert call_args.kwargs["thread_id"] == "test-deps-thread"
            assert call_args.kwargs["round_number"] == 1
            assert call_args.kwargs["node"] == "executor"
    finally:
        workspace_file.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_executor_agent_native_pydantic_ai_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """executor_agent runs end-to-end through Pydantic AI when LLM_PROVIDER=test."""
    monkeypatch.setenv("LLM_PROVIDER", "test")
    audit_mock = AsyncMock()
    monkeypatch.setattr("agent.executor.write_audit_event", audit_mock)

    state = {
        "thread_id": "thread-native-pydantic",
        "task": "Test feature",
        "messages": [],
        "plan": ["step 1"],
        "rounds": 0,
        "max_rounds": 3,
        "role": "executor",
        "approved": False,
        "human_in_the_loop": False,
    }

    result = await executor_agent(state)
    assert result["role"] == "executor"
    assert "execution" in result
    assert "summary" in result["execution"]
    assert "messages" in result
    assert any("Executor summary:" in getattr(m, "content", "") for m in result["messages"])


@pytest.mark.asyncio
async def test_executor_includes_superpowers_execution_directives() -> None:
    """Executor system prompt and agent configuration embody Superpowers execution rules."""
    agent = create_executor_agent(model=TestModel())
    system_prompt = agent._system_prompts[0] if agent._system_prompts else ""
    assert "Superpowers" in system_prompt
    assert "Evidence Over Claims" in system_prompt
    assert "The Plan Did The Thinking" in system_prompt
