"""Tests for executor tool registry defaults and thread binding."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.thread_artifacts import init_thread_artifacts
from tools.registry import DEFAULT_ALLOWED_TOOLS, get_executor_tools


def test_default_allowlist_includes_thread_file_tools() -> None:
    """Default EXECUTOR_TOOLS includes write/read thread file tools."""
    assert "write_thread_file" in DEFAULT_ALLOWED_TOOLS
    assert "read_thread_file" in DEFAULT_ALLOWED_TOOLS


def test_get_executor_tools_binds_thread_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_executor_tools(thread_id) returns bound thread file tools."""
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(tmp_path))
    monkeypatch.delenv("EXECUTOR_TOOLS", raising=False)
    init_thread_artifacts("t", "tid-reg", plan=[])
    tools = get_executor_tools("tid-reg")
    names = {t.name for t in tools}
    assert "write_thread_file" in names
    assert "read_file" in names
