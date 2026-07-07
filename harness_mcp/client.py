"""MCP client session manager and tool invocation."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from harness_mcp.schemas import McpStdioServerConfig, McpToolDescriptor

logger = logging.getLogger(__name__)

_manager: McpClientManager | None = None


def qualify_tool_name(server: str, tool_name: str) -> str:
    """Build a stable executor tool name for an MCP tool."""
    safe_server = server.replace("-", "_")
    safe_tool = tool_name.replace("-", "_")
    return f"mcp__{safe_server}__{safe_tool}"


def format_call_tool_result(result: object) -> str:
    """Serialize an MCP CallToolResult for LLM tool messages."""
    is_error = bool(getattr(result, "isError", False))
    content_blocks = getattr(result, "content", []) or []
    parts: list[str] = []
    for block in content_blocks:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(str(text))
        else:
            parts.append(str(block))

    structured = getattr(result, "structuredContent", None)
    if structured is not None and not parts:
        parts.append(json.dumps(structured, default=str))

    body = "\n".join(parts).strip()
    if not body and structured is not None:
        body = json.dumps(structured, default=str)
    if not body:
        body = "(empty MCP tool result)"
    if is_error:
        return f"error: {body}"
    return body


class McpClientManager:
    """Maintain stdio MCP sessions for configured servers."""

    def __init__(self, servers: dict[str, McpStdioServerConfig]) -> None:
        self._servers = servers
        self._sessions: dict[str, ClientSession] = {}
        self._stack = AsyncExitStack()
        self._lock = asyncio.Lock()
        self._connected = False

    @property
    def server_names(self) -> list[str]:
        """Return configured server names."""
        return sorted(self._servers)

    async def connect(self) -> None:
        """Open stdio sessions for all configured servers."""
        async with self._lock:
            if self._connected:
                return

            for name, cfg in self._servers.items():
                params = StdioServerParameters(
                    command=cfg.command,
                    args=cfg.args,
                    env=cfg.env,
                    cwd=cfg.cwd,
                )
                read, write = await self._stack.enter_async_context(
                    stdio_client(params),
                )
                session = await self._stack.enter_async_context(
                    ClientSession(read, write),
                )
                await session.initialize()
                self._sessions[name] = session
                logger.info("Connected MCP server %s", name)

            self._connected = True

    async def shutdown(self) -> None:
        """Close all MCP sessions."""
        async with self._lock:
            self._sessions.clear()
            await self._stack.aclose()
            self._connected = False

    async def list_tools(self) -> list[McpToolDescriptor]:
        """List tools from every connected MCP server."""
        await self.connect()
        descriptors: list[McpToolDescriptor] = []
        for server, session in self._sessions.items():
            listed = await session.list_tools()
            for tool in listed.tools:
                descriptors.append(
                    McpToolDescriptor(
                        server=server,
                        name=tool.name,
                        qualified_name=qualify_tool_name(server, tool.name),
                        description=tool.description or "",
                        input_schema=dict(tool.inputSchema or {}),
                    ),
                )
        return descriptors

    async def call_tool(
        self,
        *,
        server: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> str:
        """Invoke a tool on a connected MCP server."""
        await self.connect()
        if server not in self._sessions:
            msg = f"Unknown MCP server: {server}"
            raise KeyError(msg)

        session = self._sessions[server]
        result = await session.call_tool(tool_name, arguments=arguments or {})
        return format_call_tool_result(result)


def get_mcp_manager() -> McpClientManager | None:
    """Return the process-wide MCP manager when configured."""
    return _manager


async def init_mcp_manager(servers: dict[str, McpStdioServerConfig]) -> McpClientManager | None:
    """Create the global MCP manager when servers are configured."""
    global _manager
    if not servers:
        _manager = None
        return None

    if _manager is not None:
        return _manager

    _manager = McpClientManager(servers)
    await _manager.connect()
    return _manager


async def shutdown_mcp_manager() -> None:
    """Close the global MCP manager."""
    global _manager
    if _manager is None:
        return
    await _manager.shutdown()
    _manager = None
