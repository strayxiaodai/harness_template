"""Schemas for harness skill distillation."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SkillDraft(BaseModel):
    """Structured output from the skill distillation LLM."""

    name: str = Field(
        min_length=1,
        description="Kebab-case skill directory name, e.g. add-sqlite-checkpoints",
    )
    description: str = Field(
        min_length=1,
        description="One-line description for SKILL.md frontmatter and discovery",
    )
    body: str = Field(
        min_length=1,
        description="Markdown body for SKILL.md (no YAML frontmatter)",
    )


class HarnessSkillMeta(BaseModel):
    """Provenance metadata stored beside each distilled skill."""

    thread_ids: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    distilled_at: list[str] = Field(default_factory=list)
    rounds: list[int] = Field(default_factory=list)


class SkillSummary(BaseModel):
    """Summary row for GET /skills."""

    slug: str
    name: str
    description: str
    path: str
    thread_count: int
    updated_at: datetime | None = None


class DistillSkillRequest(BaseModel):
    """Request body for POST /skills/distill."""

    thread_id: str = Field(min_length=1)
    name: str | None = Field(
        default=None,
        description="Optional slug override; auto-derived from task when omitted",
    )
    refine: bool = Field(
        default=True,
        description="Merge with an existing skill at the same slug when present",
    )


class DistillSkillResponse(BaseModel):
    """Response body for POST /skills/distill and POST /skills/save."""

    thread_id: str
    slug: str
    path: str | None = None
    saved: bool
    created: bool
    refined: bool
    description: str
    name: str
    body: str
    status: str
