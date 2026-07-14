"""Thread-scoped read/write tools bound to a thread_id."""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from app.services.thread_artifacts import lookup_thread_dir

_MAX_BYTES = 131072


def _thread_root(thread_id: str) -> Path:
    """Resolve the on-disk root for a thread_id."""
    root = lookup_thread_dir(thread_id)
    if root is None:
        raise FileNotFoundError(f"no thread dir for {thread_id!r}")
    return root.resolve()


def resolve_scripts_path(thread_id: str, relative: str) -> Path:
    """Resolve a path under ``scripts/``; reject escapes."""
    if not relative or relative.startswith("/") or ".." in Path(relative).parts:
        raise ValueError("invalid scripts path")
    scripts = (_thread_root(thread_id) / "scripts").resolve()
    scripts.mkdir(parents=True, exist_ok=True)
    target = (scripts / relative).resolve()
    if not target.is_relative_to(scripts):
        raise ValueError("path escapes scripts/")
    return target


def resolve_thread_path(thread_id: str, relative: str) -> Path:
    """Resolve a path under the thread dir for reads."""
    if not relative or relative.startswith("/") or ".." in Path(relative).parts:
        raise ValueError("invalid thread path")
    root = _thread_root(thread_id)
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError("path escapes thread dir")
    return target


class WriteThreadFileInput(BaseModel):
    """Input for write_thread_file."""

    path: str = Field(
        description="Path relative to scripts/ (*.py or manifest.json)"
    )
    content: str = Field(description="Full file contents to write")


class ReadThreadFileInput(BaseModel):
    """Input for read_thread_file."""

    path: str = Field(description="Path relative to the thread directory")
    max_bytes: int = Field(default=8192, ge=1, le=_MAX_BYTES)


def make_write_thread_file(thread_id: str) -> BaseTool:
    """Build write_thread_file closed over ``thread_id``."""

    @tool("write_thread_file", args_schema=WriteThreadFileInput)
    async def write_thread_file(path: str, content: str) -> str:
        """Write a Python module or manifest.json under this thread's scripts/."""
        target = resolve_scripts_path(thread_id, path)
        if path == "manifest.json":
            pass
        elif path.endswith(".py"):
            pass
        else:
            raise ValueError("only *.py or manifest.json may be written")
        raw = content.encode("utf-8")
        if len(raw) > _MAX_BYTES:
            raise ValueError(f"content exceeds {_MAX_BYTES} bytes")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote scripts/{path} ({len(raw)} bytes)"

    return write_thread_file


def make_read_thread_file(thread_id: str) -> BaseTool:
    """Build read_thread_file closed over ``thread_id``."""

    @tool("read_thread_file", args_schema=ReadThreadFileInput)
    async def read_thread_file(path: str, max_bytes: int = 8192) -> str:
        """Read a file from this thread's artifact directory."""
        target = resolve_thread_path(thread_id, path)
        if not target.is_file():
            raise FileNotFoundError(path)
        return target.read_bytes()[:max_bytes].decode("utf-8", errors="replace")

    return read_thread_file
