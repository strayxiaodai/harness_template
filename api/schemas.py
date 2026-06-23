"""API request and response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunRequest(BaseModel):
    """Request body for graph execution."""

    task: str = ""
    thread_id: str = Field(min_length=1)
    plan: list[str] = Field(default_factory=list)
    max_rounds: int = Field(default=3, ge=1, le=20)
    timeout_seconds: float = Field(default=120.0, ge=1.0, le=900.0)
    human_in_the_loop: bool = False
    skill_slug: str | None = Field(
        default=None,
        description="Apply a saved harness skill playbook to this run",
    )

    @model_validator(mode="after")
    def validate_task_or_skill(self) -> RunRequest:
        """Require a task and/or a skill slug."""
        if not self.task.strip() and not self.skill_slug:
            msg = "Either task or skill_slug is required"
            raise ValueError(msg)
        return self


class ReviewOverride(BaseModel):
    """Typed review override for HITL correction."""

    verdict: Literal["pass", "fail"]
    reason: str = Field(min_length=1)
    suggested_step: Literal["planner", "executor", "finish"]


class ResumeOverrides(BaseModel):
    """Allowed state edits before a HITL thread resumes."""

    model_config = ConfigDict(extra="forbid")

    plan: list[str] | None = None
    task: str | None = None
    result: str | None = None
    review: ReviewOverride | None = None
    refine_from: Literal["planner", "executor", "finish"] | None = None


class ResumeRequest(BaseModel):
    """Request body for /resume during human-in-the-loop runs."""

    thread_id: str = Field(min_length=1)
    timeout_seconds: float = Field(default=120.0, ge=1.0, le=900.0)
    overrides: ResumeOverrides | None = None


class RunResponse(BaseModel):
    """Response body for graph execution and resume."""

    thread_id: str
    status: Literal["complete", "awaiting_human"]
    approved: bool
    needs_human: bool = False
    result: str | None = None
    next_action: str | None = None
    last_role: str | None = None
    rounds: int = 0
    max_rounds: int = 0


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
