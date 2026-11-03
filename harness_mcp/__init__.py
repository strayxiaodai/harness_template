"""Model Context Protocol (MCP) client integration for the harness via PydanticAI."""

from harness_mcp.client import (
    McpClientManager,
    get_mcp_manager,
    shutdown_mcp_manager,
)
from harness_mcp.config import load_mcp_server_configs
from harness_mcp.tools import (
    get_cached_mcp_tools,
    get_cached_mcp_toolsets,
    init_mcp_tools,
)

__all__ = [
    "McpClientManager",
    "get_cached_mcp_tools",
    "get_cached_mcp_toolsets",
    "get_mcp_manager",
    "init_mcp_tools",
    "load_mcp_server_configs",
    "shutdown_mcp_manager",
]
