"""Schemas for thread artifact list endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ThreadSummary(BaseModel):
    """Summary row for GET /threads."""

    thread_id: str
    task: str
    slug: str
    started_at: str = ""
    plan: list[str] = Field(default_factory=list)
