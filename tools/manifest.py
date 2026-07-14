"""Parse and validate scripts/manifest.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ManifestEntry:
    """One runnable script listed by the executor."""

    path: str
    purpose: str = ""
    args: list[str] = field(default_factory=list)


def load_manifest(scripts_dir: Path) -> list[ManifestEntry]:
    """Return entries from manifest.json, or [] if missing/invalid."""
    path = scripts_dir / "manifest.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    out: list[ManifestEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        if not isinstance(rel, str) or not rel.endswith(".py"):
            continue
        if ".." in Path(rel).parts or rel.startswith("/"):
            continue
        purpose = item.get("purpose") if isinstance(item.get("purpose"), str) else ""
        args_raw = item.get("args") or []
        args = [str(a) for a in args_raw] if isinstance(args_raw, list) else []
        out.append(ManifestEntry(path=rel, purpose=purpose, args=args))
    return out


def require_entry(scripts_dir: Path, rel_path: str) -> ManifestEntry:
    """Return the manifest entry for ``rel_path`` or raise PermissionError."""
    for entry in load_manifest(scripts_dir):
        if entry.path == rel_path:
            return entry
    raise PermissionError(f"{rel_path!r} is not listed in manifest.json")
