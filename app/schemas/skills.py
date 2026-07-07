"""Schemas for skill library endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
    save: bool = Field(
        default=False,
        description="Write SKILL.md to disk; false returns a preview only",
    )


class SaveSkillRequest(BaseModel):
    """Request body for POST /skills/save after preview."""

    thread_id: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    body: str = Field(min_length=1)


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
    status: Literal["complete", "in_progress"]


class SkillSummary(BaseModel):
    """Summary row for GET /skills."""

    slug: str
    name: str
    description: str
    path: str
    thread_count: int
    updated_at: str | None = None


class SkillDetail(BaseModel):
    """Full skill payload for GET /skills/{slug}."""

    slug: str
    name: str
    description: str
    path: str
    body: str
    thread_count: int
    updated_at: str | None = None
