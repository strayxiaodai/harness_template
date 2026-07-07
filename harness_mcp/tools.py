"""Expose MCP tools as LangChain executor tools."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import Field, create_model

from harness_mcp.client import (
    McpClientManager,
    get_mcp_manager,
    init_mcp_manager,
    qualify_tool_name,
)
from harness_mcp.config import load_mcp_server_configs
from harness_mcp.schemas import McpToolDescriptor

logger = logging.getLogger(__name__)

_cached_tools: list[BaseTool] = []
_cached_by_name: dict[str, BaseTool] = {}


def _json_schema_to_fields(schema: dict[str, object]) -> dict[str, Any]:
    """Map a small JSON-schema object to Pydantic fields for StructuredTool."""
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}

    required = schema.get("required")
    required_names = set(required) if isinstance(required, list) else set()
    fields: dict[str, Any] = {}
    for name, spec in properties.items():
        if not isinstance(spec, dict):
            continue
        description = str(spec.get("description", ""))
        field_type: Any = str
        json_type = spec.get("type")
        if json_type == "integer":
            field_type = int
        elif json_type == "number":
            field_type = float
        elif json_type == "boolean":
            field_type = bool
        elif json_type == "object":
            field_type = dict[str, Any]
        elif json_type == "array":
            field_type = list[Any]

        if name in required_names:
            fields[name] = (field_type, Field(description=description))
        else:
            fields[name] = (field_type | None, Field(default=None, description=description))
    return fields


def _build_langchain_tool(
    manager: McpClientManager,
    descriptor: McpToolDescriptor,
) -> StructuredTool:
    """Wrap one MCP tool as a LangChain StructuredTool."""
    fields = _json_schema_to_fields(descriptor.input_schema)
    args_model = create_model(f"{descriptor.qualified_name}_args", **fields)

    async def _invoke(**kwargs: Any) -> str:
        clean = {key: value for key, value in kwargs.items() if value is not None}
        return await manager.call_tool(
            server=descriptor.server,
            tool_name=descriptor.name,
            arguments=clean,
        )

    description = descriptor.description or (
        f"MCP tool {descriptor.name} from server {descriptor.server}"
    )
    return StructuredTool.from_function(
        coroutine=_invoke,
        name=descriptor.qualified_name,
        description=description,
        args_schema=args_model,
    )


async def init_mcp_tools() -> list[BaseTool]:
    """Discover MCP tools and cache LangChain wrappers for the executor."""
    global _cached_tools, _cached_by_name

    servers = load_mcp_server_configs()
    manager = await init_mcp_manager(servers)
    if manager is None:
        _cached_tools = []
        _cached_by_name = {}
        return []

    descriptors = await manager.list_tools()
    tools = [_build_langchain_tool(manager, descriptor) for descriptor in descriptors]
    _cached_tools = tools
    _cached_by_name = {tool.name: tool for tool in tools}
    logger.info("Registered %d MCP tool(s) for executor", len(tools))
    return tools


def get_cached_mcp_tools() -> list[BaseTool]:
    """Return MCP tools registered at startup."""
    return list(_cached_tools)


def get_cached_mcp_tool(name: str) -> BaseTool | None:
    """Look up a cached MCP tool by qualified name."""
    return _cached_by_name.get(name)


def parse_mcp_tool_name(qualified_name: str) -> tuple[str, str] | None:
    """Parse ``mcp__{server}__{tool}`` back into server and tool names."""
    if not qualified_name.startswith("mcp__"):
        return None
    parts = qualified_name.split("__", 2)
    if len(parts) != 3:
        return None
    return parts[1], parts[2]
