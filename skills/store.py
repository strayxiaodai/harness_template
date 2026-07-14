"""Filesystem helpers for harness skill library."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

from skills.schemas import HarnessSkillMeta, SkillSummary

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_META_FILENAME = "harness.json"
_SKILL_FILENAME = "SKILL.md"
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def skills_root() -> Path:
    """Return the directory where distilled skills are written."""
    override = os.getenv("HARNESS_SKILLS_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _REPO_ROOT / "app" / "skills"


def slugify(text: str, *, max_length: int = 48) -> str:
    """Convert arbitrary text into a kebab-case skill slug."""
    lowered = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if not slug:
        slug = "harness-task"
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug


def normalize_slug(name: str) -> str:
    """Validate and normalize a user-provided skill slug."""
    slug = slugify(name)
    if not _SLUG_RE.match(slug):
        msg = f"Invalid skill slug: {name!r}"
        raise ValueError(msg)
    return slug


def skill_dir(slug: str, *, root: Path | None = None) -> Path:
    """Return the directory for a skill slug."""
    base = root or skills_root()
    return base / slug


def skill_path(slug: str, *, root: Path | None = None) -> Path:
    """Return the SKILL.md path for a slug."""
    return skill_dir(slug, root=root) / _SKILL_FILENAME


def meta_path(slug: str, *, root: Path | None = None) -> Path:
    """Return the harness provenance path for a slug."""
    return skill_dir(slug, root=root) / _META_FILENAME


def read_skill(slug: str, *, root: Path | None = None) -> tuple[str, str, str]:
    """Read name, description, and body from an on-disk skill.

    Returns:
        Tuple of (name, description, body markdown).
    """
    path = skill_path(slug, root=root)
    if not path.is_file():
        msg = f"Skill not found: {slug}"
        raise FileNotFoundError(msg)

    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return slug, slug, raw.strip()

    _, frontmatter, body = raw.split("---", 2)
    meta = yaml.safe_load(frontmatter) or {}
    name = str(meta.get("name", slug))
    description = str(meta.get("description", ""))
    return name, description, body.strip()


def read_meta(slug: str, *, root: Path | None = None) -> HarnessSkillMeta:
    """Load harness provenance for a skill."""
    path = meta_path(slug, root=root)
    if not path.is_file():
        return HarnessSkillMeta()
    data = json.loads(path.read_text(encoding="utf-8"))
    return HarnessSkillMeta.model_validate(data)


def write_skill(
    slug: str,
    *,
    name: str,
    description: str,
    body: str,
    thread_id: str,
    task: str,
    rounds: int,
    root: Path | None = None,
) -> Path:
    """Write SKILL.md and update harness provenance."""
    base = skill_dir(slug, root=root)
    base.mkdir(parents=True, exist_ok=True)

    frontmatter = {
        "name": name,
        "description": description,
    }
    content = (
        "---\n"
        f"{yaml.safe_dump(frontmatter, sort_keys=False).strip()}\n"
        "---\n\n"
        f"{body.strip()}\n"
    )
    path = base / _SKILL_FILENAME
    path.write_text(content, encoding="utf-8")

    meta = read_meta(slug, root=root)
    if thread_id not in meta.thread_ids:
        meta.thread_ids.append(thread_id)
    if task and task not in meta.tasks:
        meta.tasks.append(task)
    meta.distilled_at.append(datetime.now(UTC).isoformat())
    meta.rounds.append(rounds)
    meta_path(slug, root=root).write_text(
        meta.model_dump_json(indent=2),
        encoding="utf-8",
    )

    logger.info("Wrote harness skill %s at %s", slug, path)
    return path


def list_skills(*, root: Path | None = None) -> list[SkillSummary]:
    """List distilled skills in the library."""
    base = root or skills_root()
    if not base.is_dir():
        return []

    summaries: list[SkillSummary] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        skill_file = child / _SKILL_FILENAME
        if not skill_file.is_file():
            continue
        slug = child.name
        try:
            name, description, _ = read_skill(slug, root=base)
        except OSError:
            continue
        meta = read_meta(slug, root=base)
        updated_at = None
        if meta.distilled_at:
            updated_at = datetime.fromisoformat(meta.distilled_at[-1])
        summaries.append(
            SkillSummary(
                slug=slug,
                name=name,
                description=description,
                path=str(skill_file),
                thread_count=len(meta.thread_ids),
                updated_at=updated_at,
            ),
        )
    return summaries
