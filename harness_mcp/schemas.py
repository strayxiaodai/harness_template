"""Schemas for MCP server configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class McpStdioServerConfig(BaseModel):
    """Stdio transport settings for one MCP server."""

    transport: Literal["stdio"] = "stdio"
    command: str = Field(min_length=1)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] | None = None
    cwd: str | None = None


class McpServersDocument(BaseModel):
    """Cursor-compatible MCP servers file shape."""

    mcpServers: dict[str, McpStdioServerConfig] = Field(default_factory=dict)


class McpToolDescriptor(BaseModel):
    """One tool exposed by an MCP server."""

    server: str
    name: str
    qualified_name: str
    description: str = ""
    input_schema: dict[str, object] = Field(default_factory=dict)
