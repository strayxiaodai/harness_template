"""Tests for PydanticAI-compatible HarnessTool wrappers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from tools.base import HarnessTool, harness_tool
from tools.code_tools import list_dir, read_file
from tools.registry import get_executor_tools


class CustomInput(BaseModel):
    query: str = Field(description="Search query")


@harness_tool("custom_search", args_schema=CustomInput)
async def custom_search(query: str) -> str:
    """Search for items matching query."""
    return f"found results for {query}"


@pytest.mark.asyncio
async def test_harness_tool_direct_call() -> None:
    """HarnessTool can be called directly as an async function."""
    res = await custom_search(query="python")
    assert res == "found results for python"


@pytest.mark.asyncio
async def test_harness_tool_ainvoke_dict() -> None:
    """HarnessTool supports LangChain ainvoke with dict."""
    res = await custom_search.ainvoke({"query": "pydantic"})
    assert res == "found results for pydantic"


@pytest.mark.asyncio
async def test_harness_tool_ainvoke_model() -> None:
    """HarnessTool supports LangChain ainvoke with BaseModel input."""
    res = await custom_search.ainvoke(CustomInput(query="models"))
    assert res == "found results for models"


@pytest.mark.asyncio
async def test_harness_tool_used_in_pydantic_ai_agent() -> None:
    """PydanticAI Agent accepts HarnessTool directly."""
    model = TestModel(call_tools=["custom_search"], custom_output_text="search completed")
    agent = Agent(model, tools=[custom_search])

    result = await agent.run("Find python items")
    assert result.output == "search completed"
    messages = result.all_messages()
    assert len(messages) >= 3


@pytest.mark.asyncio
async def test_executor_tools_registered_with_pydantic_ai(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tools from registry can be bound directly to a PydanticAI Agent."""
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(tmp_path))
    monkeypatch.delenv("EXECUTOR_TOOLS", raising=False)

    tools = get_executor_tools("test-thread-pydantic")
    assert len(tools) >= 2

    test_file = Path.cwd() / "a"
    test_file.write_text("hello executor", encoding="utf-8")
    try:
        model = TestModel(
            call_tools=["read_file"],
            custom_output_text="done",
        )
        agent = Agent(model, tools=tools)
        assert len(agent._function_toolset.tools) >= 2

        # Agent runs and uses the registered tools
        res = await agent.run("read the file")
        assert res.output == "done"
    finally:
        test_file.unlink(missing_ok=True)
