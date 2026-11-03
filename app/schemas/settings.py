"""Schemas for settings and runtime configuration endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class McpServerDetail(BaseModel):
    """Configuration detail for one MCP server."""

    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class McpInfo(BaseModel):
    """Runtime status and server list for Model Context Protocol."""

    enabled: bool = False
    servers: dict[str, McpServerDetail] = Field(default_factory=dict)
    tools: list[str] = Field(default_factory=list)


class SystemSettingsResponse(BaseModel):
    """System-level and agent loop configuration response."""

    task_rewrite_enabled: bool = False
    human_in_the_loop_default: bool = True
    mcp: McpInfo = Field(default_factory=McpInfo)
    llm_provider: str = "openai"
    checkpoint_backend: str = "sqlite"
    rag_enabled: bool = False
    rag_rewrite_enabled: bool = True

