"""Tests for learner run_thread_script tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.thread_artifacts import init_thread_artifacts
from tools.registry import get_learner_tools
from tools.sandbox_docker import DockerRunResult


@pytest.fixture
def thread_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Thread dir with a listed script and manifest."""
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(tmp_path))
    root = init_thread_artifacts("s", "tid-script", plan=[])
    scripts = root / "scripts"
    scripts.mkdir(exist_ok=True)
    (scripts / "ok.py").write_text("print('hi')\n", encoding="utf-8")
    (scripts / "manifest.json").write_text(
        json.dumps({"entries": [{"path": "ok.py", "purpose": "smoke"}]}),
        encoding="utf-8",
    )
    return root


@pytest.mark.asyncio
async def test_run_thread_script_uses_docker(
    thread_dir: Path,
) -> None:
    """run_thread_script delegates to Docker runner for listed paths."""
    tools = {t.name: t for t in get_learner_tools("tid-script")}
    assert "write_thread_file" not in tools
    assert "run_thread_script" in tools

    with patch(
        "tools.script_tools.run_python_in_docker",
        return_value=DockerRunResult(
            status="ok", exit_code=0, stdout="hi\n", stderr=""
        ),
    ) as mocked:
        out = await tools["run_thread_script"].ainvoke({"path": "ok.py"})
    mocked.assert_called_once()
    assert "hi" in out


@pytest.mark.asyncio
async def test_run_rejects_unlisted(thread_dir: Path) -> None:
    """Unlisted scripts raise PermissionError before Docker."""
    tools = {t.name: t for t in get_learner_tools("tid-script")}
    with pytest.raises(PermissionError):
        await tools["run_thread_script"].ainvoke({"path": "other.py"})
