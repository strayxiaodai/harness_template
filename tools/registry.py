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

_THREAD_TOOL_NAMES = frozenset({"write_thread_file", "read_thread_file"})

DEFAULT_ALLOWED_TOOLS = (
    "read_file,list_dir,write_thread_file,read_thread_file"
)


def _allowlist() -> set[str]:
    """Read EXECUTOR_TOOLS (comma-separated). Default includes thread file tools."""
    raw = os.getenv("EXECUTOR_TOOLS", DEFAULT_ALLOWED_TOOLS)
    allowed = {name.strip() for name in raw.split(",") if name.strip()}
    include_mcp = os.getenv("HARNESS_MCP_INCLUDE_ALL", "true").strip().lower()
    if include_mcp in {"1", "true", "yes"}:
        for tool in get_cached_mcp_tools():
            allowed.add(tool.name)
    return allowed


def _builtin_tools() -> dict[str, BaseTool]:
    """Return built-in static executor tools keyed by name."""
    return dict(_ALL_TOOLS)


def _executor_tool_map() -> dict[str, BaseTool]:
    """Merge built-in and MCP tools for the current process."""
    tools = _builtin_tools()
    for tool in get_cached_mcp_tools():
        tools[tool.name] = tool
    return tools


def get_executor_tools(thread_id: str) -> list[BaseTool]:
    """Return executor tools; thread-scoped tools bound to ``thread_id``."""
    from tools.thread_files import make_read_thread_file, make_write_thread_file

    allowed = _allowlist()
    available = _executor_tool_map()
    if "write_thread_file" in allowed:
        available["write_thread_file"] = make_write_thread_file(thread_id)
    if "read_thread_file" in allowed:
        available["read_thread_file"] = make_read_thread_file(thread_id)
    missing = allowed - set(available)
    if missing:
        raise RuntimeError(
            f"Unknown tools in EXECUTOR_TOOLS: {sorted(missing)}"
        )
    return [available[name] for name in sorted(allowed)]


def get_learner_tools(thread_id: str) -> list[BaseTool]:
    """Tools the learner may call (read + sandboxed run only)."""
    from tools.script_tools import make_run_thread_script
    from tools.thread_files import make_read_thread_file

    return [
        make_read_thread_file(thread_id),
        make_run_thread_script(thread_id),
    ]


def get_tool_by_name(name: str, thread_id: str | None = None) -> BaseTool:
    """Look up a tool by name. Thread tools require ``thread_id``."""
    if name in _THREAD_TOOL_NAMES or name == "run_thread_script":
        if not thread_id:
            raise PermissionError(f"tool {name!r} requires thread_id")
        tools = (
            get_learner_tools(thread_id)
            if name == "run_thread_script"
            else get_executor_tools(thread_id)
        )
        for tool in tools:
            if tool.name == name:
                return tool
        raise KeyError(f"tool {name!r} is not registered")
    if name not in _allowlist():
        raise PermissionError(f"tool {name!r} is not in the allow-list")
    tool = _executor_tool_map().get(name)
    if tool is None:
        raise KeyError(f"tool {name!r} is not registered")
    return tool
