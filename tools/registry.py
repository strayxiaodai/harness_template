# app/tools/registry.py
import os

from langchain_core.tools import BaseTool

from tools.code_tools import list_dir, read_file
from tools.rag_tools import search_knowledge_base

try:
    from harness_mcp.tools import get_cached_mcp_tool, get_cached_mcp_tools
except ImportError:  # pragma: no cover - optional dependency
    def get_cached_mcp_tools() -> list[BaseTool]:
        return []

    def get_cached_mcp_tool(name: str) -> BaseTool | None:
        return None

_ALL_TOOLS: dict[str, BaseTool] = {
    read_file.name: read_file,
    list_dir.name: list_dir,
    search_knowledge_base.name: search_knowledge_base,
}

DEFAULT_ALLOWED_TOOLS = "read_file,list_dir"


def _allowlist() -> set[str]:
    """Read EXECUTOR_TOOLS (comma-separated). Default: read-only tools."""
    raw = os.getenv("EXECUTOR_TOOLS", DEFAULT_ALLOWED_TOOLS)
    allowed = {name.strip() for name in raw.split(",") if name.strip()}
    include_mcp = os.getenv("HARNESS_MCP_INCLUDE_ALL", "true").strip().lower()
    if include_mcp in {"1", "true", "yes"}:
        for tool in get_cached_mcp_tools():
            allowed.add(tool.name)
    return allowed


def _builtin_tools() -> dict[str, BaseTool]:
    """Return built-in executor tools keyed by name."""
    return dict(_ALL_TOOLS)


def _executor_tool_map() -> dict[str, BaseTool]:
    """Merge built-in and MCP tools for the current process."""
    tools = _builtin_tools()
    for tool in get_cached_mcp_tools():
        tools[tool.name] = tool
    return tools


def get_executor_tools() -> list[BaseTool]:
    """Return the tools the executor is allowed to call."""
    allowed = _allowlist()
    available = _executor_tool_map()
    missing = allowed - set(available)
    if missing:
        raise RuntimeError(
            f"Unknown tools in EXECUTOR_TOOLS: {sorted(missing)}"
        )
    return [available[name] for name in sorted(allowed)]


def get_tool_by_name(name: str) -> BaseTool:
    """Look up a tool by name. Raises if missing or not allow-listed."""
    if name not in _allowlist():
        raise PermissionError(f"tool {name!r} is not in the allow-list")
    tool = _executor_tool_map().get(name)
    if tool is None:
        raise KeyError(f"tool {name!r} is not registered")
    return tool