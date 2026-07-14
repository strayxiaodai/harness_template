"""Tests for Docker S2 sandbox runner (mocked subprocess)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tools.sandbox_docker import run_python_in_docker


def test_run_builds_secure_docker_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """docker run argv includes network=none, read-only, and cap-drop."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "a.py").write_text("print(1)\n", encoding="utf-8")

    completed = MagicMock()
    completed.returncode = 0
    completed.stdout = b"1\n"
    completed.stderr = b""

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        assert cmd[0] == "docker"
        assert "run" in cmd
        assert "--network=none" in cmd
        assert "--read-only" in cmd
        assert "--cap-drop=ALL" in cmd
        assert any(str(scripts.resolve()) in part for part in cmd)
        return completed

    monkeypatch.setattr("tools.sandbox_docker.subprocess.run", fake_run)
    result = run_python_in_docker(scripts, "a.py", args=[])
    assert result.exit_code == 0
    assert result.stdout.strip() == "1"
    assert result.status == "ok"


def test_docker_missing_hard_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing Docker CLI returns status=error without host fallback."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "a.py").write_text("print(1)\n", encoding="utf-8")

    def boom(*_a: object, **_k: object) -> None:
        raise FileNotFoundError("docker")

    monkeypatch.setattr("tools.sandbox_docker.subprocess.run", boom)
    result = run_python_in_docker(scripts, "a.py", args=[])
    assert result.status == "error"
    assert "docker" in result.message.lower()


def test_timeout_sets_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TimeoutExpired becomes status=error with null exit_code."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "a.py").write_text("print(1)\n", encoding="utf-8")

    def boom(*_a: object, **_k: object) -> None:
        raise subprocess.TimeoutExpired(cmd="docker", timeout=1)

    monkeypatch.setattr("tools.sandbox_docker.subprocess.run", boom)
    result = run_python_in_docker(scripts, "a.py", args=[], timeout_seconds=1)
    assert result.status == "error"
    assert result.exit_code is None
