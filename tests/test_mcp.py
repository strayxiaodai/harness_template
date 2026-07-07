"""Tests for MCP client integration."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from harness_mcp.client import McpClientManager, format_call_tool_result, qualify_tool_name
from harness_mcp.config import load_mcp_server_configs
from harness_mcp.schemas import McpStdioServerConfig, McpToolDescriptor
from harness_mcp.tools import parse_mcp_tool_name


def test_qualify_tool_name() -> None:
    """Qualified names are stable and namespaced."""
    assert qualify_tool_name("context7", "resolve-library-id") == (
        "mcp__context7__resolve_library_id"
    )


def test_parse_mcp_tool_name_round_trip() -> None:
    """Qualified MCP tool names parse back to server and tool."""
    assert parse_mcp_tool_name("mcp__demo__search") == ("demo", "search")
    assert parse_mcp_tool_name("read_file") is None


def test_format_call_tool_result_text() -> None:
    """Text MCP content is flattened for executor tool messages."""
    block = MagicMock()
    block.text = "hello"
    result = MagicMock(isError=False, content=[block], structuredContent=None)
    assert format_call_tool_result(result) == "hello"


def test_format_call_tool_result_error() -> None:
    """MCP errors are prefixed for the executor."""
    block = MagicMock()
    block.text = "boom"
    result = MagicMock(isError=True, content=[block], structuredContent=None)
    assert format_call_tool_result(result) == "error: boom"


def test_load_mcp_server_configs_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit disable returns no servers."""
    monkeypatch.setenv("HARNESS_MCP_ENABLED", "false")
    assert load_mcp_server_configs() == {}


def test_load_mcp_server_configs_inline_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inline JSON env configures MCP servers."""
    monkeypatch.delenv("HARNESS_MCP_ENABLED", raising=False)
    monkeypatch.setenv(
        "HARNESS_MCP_SERVERS",
        json.dumps(
            {
                "demo": {
                    "command": "python",
                    "args": ["-m", "demo_mcp"],
                },
            },
        ),
    )
    servers = load_mcp_server_configs()
    assert "demo" in servers
    assert servers["demo"].command == "python"


@pytest.mark.asyncio
async def test_mcp_client_manager_call_tool() -> None:
    """Manager delegates tool calls to the server session."""
    manager = McpClientManager(
        {
            "demo": McpStdioServerConfig(command="python", args=["server.py"]),
        },
    )
    session = AsyncMock()
    block = MagicMock()
    block.text = "42"
    session.call_tool = AsyncMock(
        return_value=MagicMock(isError=False, content=[block], structuredContent=None),
    )
    manager._sessions = {"demo": session}
    manager._connected = True

    output = await manager.call_tool(
        server="demo",
        tool_name="add",
        arguments={"a": 1, "b": 2},
    )
    assert output == "42"
    session.call_tool.assert_awaited_once_with("add", arguments={"a": 1, "b": 2})


@pytest.mark.asyncio
async def test_build_langchain_tool_invokes_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LangChain MCP tools call through the shared manager."""
    from harness_mcp.tools import _build_langchain_tool

    manager = MagicMock()
    manager.call_tool = AsyncMock(return_value="ok")
    descriptor = McpToolDescriptor(
        server="demo",
        name="echo",
        qualified_name="mcp__demo__echo",
        description="echo back",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    )
    tool = _build_langchain_tool(manager, descriptor)
    result = await tool.ainvoke({"message": "hi"})
    assert result == "ok"
    manager.call_tool.assert_awaited_once()
