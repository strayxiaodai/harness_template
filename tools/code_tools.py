# app/tools/code_tools.py
from pathlib import Path

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ReadFileInput(BaseModel):
    """Input schema for the read_file tool."""

    path: str = Field(
        min_length=1,
        description="Workspace-relative path to read.",
    )
    max_bytes: int = Field(
        default=8192,
        ge=1,
        le=131072,
        description="Cap on bytes returned.",
    )


@tool("read_file", args_schema=ReadFileInput)
async def read_file(path: str, max_bytes: int = 8192) -> str:
    """Read up to ``max_bytes`` bytes from a workspace file."""
    workspace = Path.cwd().resolve()
    target = (workspace / path).resolve()
    if not target.is_relative_to(workspace):
        raise ValueError("path escapes the workspace")
    if not target.is_file():
        raise FileNotFoundError(path)
    return target.read_bytes()[:max_bytes].decode("utf-8", errors="replace")


class ListDirInput(BaseModel):
    """Input schema for the list_dir tool."""

    path: str = Field(
        default=".",
        description="Workspace-relative directory.",
    )


@tool("list_dir", args_schema=ListDirInput)
async def list_dir(path: str = ".") -> list[str]:
    """List entries inside a workspace directory."""
    workspace = Path.cwd().resolve()
    target = (workspace / path).resolve()
    if not target.is_relative_to(workspace) or not target.is_dir():
        raise ValueError("invalid directory")
    return sorted(p.name for p in target.iterdir())