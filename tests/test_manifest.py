"""Tests for scripts/manifest.json loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.manifest import ManifestEntry, load_manifest, require_entry


def test_load_manifest_empty_when_missing(tmp_path: Path) -> None:
    """Missing manifest yields an empty entry list."""
    assert load_manifest(tmp_path / "scripts") == []


def test_load_manifest_parses_entries(tmp_path: Path) -> None:
    """Valid manifest entries are parsed into ManifestEntry objects."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "manifest.json").write_text(
        json.dumps(
            {
                "entries": [
                    {"path": "a.py", "purpose": "check", "args": ["--x"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    entries = load_manifest(scripts)
    assert entries == [
        ManifestEntry(path="a.py", purpose="check", args=["--x"])
    ]


def test_require_entry_rejects_unknown(tmp_path: Path) -> None:
    """require_entry raises when path is not listed."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "manifest.json").write_text(
        json.dumps({"entries": [{"path": "a.py", "purpose": "p"}]}),
        encoding="utf-8",
    )
    with pytest.raises(PermissionError):
        require_entry(scripts, "b.py")
