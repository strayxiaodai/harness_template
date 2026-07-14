"""Tests for harness skills library root path."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from skills.store import skills_root, write_skill


def test_skills_root_defaults_under_app_skills() -> None:
    """Default root is <repo>/app/skills when HARNESS_SKILLS_DIR is unset."""
    os.environ.pop("HARNESS_SKILLS_DIR", None)
    root = skills_root()
    assert root.name == "skills"
    assert root.parent.name == "app"
    assert root.is_absolute()


def test_write_skill_creates_app_skills_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """write_skill creates the skills directory if missing."""
    missing = tmp_path / "skills-lib"
    assert not missing.exists()
    monkeypatch.setenv("HARNESS_SKILLS_DIR", str(missing))
    write_skill(
        "demo",
        name="demo",
        description="d",
        body="body",
        thread_id="t1",
        task="task",
        rounds=1,
        root=missing,
    )
    assert (missing / "demo" / "SKILL.md").is_file()
