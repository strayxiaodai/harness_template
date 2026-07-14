"""Tests for thread-scoped script read/write tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.thread_artifacts import init_thread_artifacts
from tools.thread_files import make_read_thread_file, make_write_thread_file


@pytest.fixture
def thread_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a thread artifact directory under a temp threads root."""
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(tmp_path))
    return init_thread_artifacts("demo task", "tid-1", plan=["a"])


@pytest.mark.asyncio
async def test_write_thread_file_creates_py_under_scripts(
    thread_dir: Path,
) -> None:
    """write_thread_file creates a .py file under scripts/."""
    tool = make_write_thread_file("tid-1")
    result = await tool.ainvoke(
        {"path": "hello.py", "content": "print(1)\n"}
    )
    assert (thread_dir / "scripts" / "hello.py").read_text(
        encoding="utf-8"
    ) == "print(1)\n"
    assert "hello.py" in result


@pytest.mark.asyncio
async def test_write_rejects_parent_escape(thread_dir: Path) -> None:
    """write_thread_file rejects path escape outside scripts/."""
    tool = make_write_thread_file("tid-1")
    with pytest.raises(ValueError, match="escape|invalid|scripts"):
        await tool.ainvoke({"path": "../meta.json", "content": "x"})


@pytest.mark.asyncio
async def test_write_allows_manifest_json(thread_dir: Path) -> None:
    """write_thread_file allows scripts/manifest.json."""
    tool = make_write_thread_file("tid-1")
    payload = json.dumps({"entries": []})
    await tool.ainvoke({"path": "manifest.json", "content": payload})
    assert (thread_dir / "scripts" / "manifest.json").is_file()


@pytest.mark.asyncio
async def test_write_rejects_non_py_non_manifest(thread_dir: Path) -> None:
    """write_thread_file rejects non-py, non-manifest files."""
    tool = make_write_thread_file("tid-1")
    with pytest.raises(ValueError):
        await tool.ainvoke({"path": "notes.txt", "content": "x"})


@pytest.mark.asyncio
async def test_read_thread_file_reads_stage_md(thread_dir: Path) -> None:
    """read_thread_file can read stage markdown under the thread dir."""
    tool = make_read_thread_file("tid-1")
    text = await tool.ainvoke({"path": "planner.md"})
    assert "planner" in text.lower()
