# app/graph/schemas.py
from typing import Literal

from pydantic import BaseModel, Field


class PlanResult(BaseModel):
    """Structured planner output written to state.plan."""

    steps: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)


class ExecutorResult(BaseModel):
    """Structured executor output consumed by the reviewer."""

    summary: str = Field(min_length=1)
    changes: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    """Structured reviewer output consumed by the actioner."""

    verdict: Literal["pass", "fail"]
    reason: str = Field(min_length=1)
    suggested_step: Literal["planner", "executor", "finish"]


class ActionScoreResult(BaseModel):
    """Structured loop quality score produced by the actioner."""

    score: int = Field(ge=0, le=100, description="Loop quality from 0-100")
    rationale: str = Field(min_length=1)