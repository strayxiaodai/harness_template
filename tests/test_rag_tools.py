"""Tests for the search_knowledge_base executor tool."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage
from app.graph.schemas import ExecutorResult
from rag.config import RagSettings
from tools.rag_tools import search_knowledge_base


def _state(**overrides: object) -> dict[str, Any]:
    """Build a minimal AgentState dict for executor tests."""
    base: dict[str, Any] = {
        "thread_id": "test-thread",
        "task": "Implement feature",
        "messages": [],
        "plan": ["step one"],
        "rounds": 0,
        "max_rounds": 3,
        "role": "executor",
        "approved": False,
        "human_in_the_loop": False,
    }
    base.update(overrides)
    return base


def _tool_call(name: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    """Build an AIMessage tool_call dict."""
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


@pytest.mark.asyncio
async def test_search_knowledge_base_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tool returns a clear message when RAG is disabled."""
    import tools.rag_tools as rag_tools_module

    monkeypatch.setattr(
        rag_tools_module,
        "load_rag_settings",
        lambda: RagSettings(enabled=False),
    )

    result = await search_knowledge_base.ainvoke({"query": "asyncio patterns"})

    assert result == "RAG is disabled."


@pytest.mark.asyncio
async def test_search_knowledge_base_calls_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tool delegates to RagService.search_documents_text."""
    import tools.rag_tools as rag_tools_module

    mock_service = MagicMock()
    mock_service.search_documents_text = AsyncMock(
        return_value="Retrieved documents:\n- [docs/IMPLEMENTATION.md] hello",
    )
    monkeypatch.setattr(
        rag_tools_module,
        "load_rag_settings",
        lambda: RagSettings(enabled=True),
    )
    monkeypatch.setattr(rag_tools_module, "get_rag_service", lambda: mock_service)

    result = await search_knowledge_base.ainvoke({"query": "hello world"})

    assert "docs/IMPLEMENTATION.md" in result
    mock_service.search_documents_text.assert_awaited_once_with("hello world")


@pytest.mark.asyncio
async def test_executor_runs_search_knowledge_base_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Executor invokes search_knowledge_base and records the tool call."""
    from app.agents import executor as executor_module
    import tools.rag_tools as rag_tools_module

    fake_llm = MagicMock()
    bound_llm = MagicMock()
    fake_llm.bind_tools.return_value = bound_llm
    fake_llm.with_structured_output.return_value = MagicMock(name="structured")
    monkeypatch.setattr(executor_module, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(
        executor_module,
        "get_executor_tools",
        lambda: [search_knowledge_base],
    )
    monkeypatch.setattr(executor_module, "write_audit_event", AsyncMock())
    monkeypatch.setenv("EXECUTOR_TOOLS", "search_knowledge_base")

    mock_service = MagicMock()
    mock_service.search_documents_text = AsyncMock(
        return_value="Retrieved documents:\n- [api.md] REST endpoints",
    )
    monkeypatch.setattr(
        rag_tools_module,
        "load_rag_settings",
        lambda: RagSettings(enabled=True),
    )
    monkeypatch.setattr(rag_tools_module, "get_rag_service", lambda: mock_service)

    tool_response = AIMessage(
        content="",
        tool_calls=[
            _tool_call(
                "search_knowledge_base",
                {"query": "REST API"},
                "call_kb_1",
            ),
        ],
    )
    follow_up = AIMessage(content="done searching")
    execution = ExecutorResult(summary="used knowledge base")
    monkeypatch.setattr(
        executor_module,
        "call_llm",
        AsyncMock(side_effect=[tool_response, follow_up, execution]),
    )

    result = await executor_module.executor_agent(_state())

    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["tool"] == "search_knowledge_base"
    assert result["tool_calls"][0]["status"] == "ok"
    mock_service.search_documents_text.assert_awaited_once_with("REST API")

    tool_messages = [
        message
        for message in result["messages"]
        if message.__class__.__name__ == "ToolMessage"
    ]
    assert len(tool_messages) == 1
    assert "REST endpoints" in tool_messages[0].content
