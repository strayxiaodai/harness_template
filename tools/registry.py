# app/tools/registry.py
import os

from langchain_core.tools import BaseTool

from tools.code_tools import list_dir, read_file
from tools.rag_tools import search_knowledge_base

_ALL_TOOLS: dict[str, BaseTool] = {
    read_file.name: read_file,
    list_dir.name: list_dir,
    search_knowledge_base.name: search_knowledge_base,
}

DEFAULT_ALLOWED_TOOLS = "read_file,list_dir"


def _allowlist() -> set[str]:
    """Read EXECUTOR_TOOLS (comma-separated). Default: read-only tools."""
    raw = os.getenv("EXECUTOR_TOOLS", DEFAULT_ALLOWED_TOOLS)
    return {name.strip() for name in raw.split(",") if name.strip()}


def get_executor_tools() -> list[BaseTool]:
    """Return the tools the executor is allowed to call."""
    allowed = _allowlist()
    missing = allowed - set(_ALL_TOOLS)
    if missing:
        raise RuntimeError(
            f"Unknown tools in EXECUTOR_TOOLS: {sorted(missing)}"
        )
    return [_ALL_TOOLS[name] for name in sorted(allowed)]


def get_tool_by_name(name: str) -> BaseTool:
    """Look up a tool by name. Raises if missing or not allow-listed."""
    if name not in _allowlist():
        raise PermissionError(f"tool {name!r} is not in the allow-list")
    return _ALL_TOOLS[name]