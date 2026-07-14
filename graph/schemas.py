# app/graph/schemas.py
from typing import Literal

from pydantic import BaseModel, Field


class PlanResult(BaseModel):
    """Structured planner output written to state.plan."""

    steps: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)


class ExecutorResult(BaseModel):
    """Structured executor output consumed by the learner."""

    summary: str = Field(min_length=1)
    changes: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)


class LessonsBlock(BaseModel):
    """Learner lessons attached for actioner scoring and UI."""

    worked: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_time: list[str] = Field(default_factory=list)


class LearningCandidate(BaseModel):
    """Memory-shaped candidate proposed by the learner."""

    id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    memory_type: Literal["fact", "preference", "entity", "summary"]
    importance: float = Field(ge=0.0, le=1.0)


class LearningResult(BaseModel):
    """Structured learner output consumed by the actioner."""

    verdict: Literal["pass", "fail"]
    reason: str = Field(min_length=1)
    suggested_step: Literal["planner", "finish"]
    lessons: LessonsBlock = Field(default_factory=LessonsBlock)
    learning_candidates: list[LearningCandidate] = Field(default_factory=list)


class ActionScoreResult(BaseModel):
    """Structured loop quality score produced by the actioner."""

    score: int = Field(ge=0, le=100, description="Loop quality from 0-100")
    rationale: str = Field(min_length=1)


class ClarificationQuestion(BaseModel):
    """One clarification prompt surfaced during HITL."""

    id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    why: str = ""


class ClarificationAnswer(BaseModel):
    """Operator answer returned through Command(resume=...)."""

    question_id: str = Field(min_length=1)
    answer: str = Field(min_length=1)