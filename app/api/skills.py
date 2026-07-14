"""Skill library routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas.skills import (
    DistillSkillRequest,
    DistillSkillResponse,
    SaveSkillRequest,
    SkillDetail,
    SkillSummary,
)
from app.services.skills import (
    distill_skill,
    get_skill_detail,
    list_skill_summaries,
    save_skill,
)
from skills.distill import SkillNotEligibleError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("", response_model=list[SkillSummary])
async def list_distilled_skills() -> list[SkillSummary]:
    """List skills distilled from prior harness threads."""
    return list_skill_summaries()


@router.get("/{slug}", response_model=SkillDetail)
async def get_distilled_skill(slug: str) -> SkillDetail:
    """Return a saved skill playbook for manual runs from the console."""
    try:
        return get_skill_detail(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/distill", response_model=DistillSkillResponse)
async def distill_skill_route(
    request: Request,
    body: DistillSkillRequest,
) -> DistillSkillResponse:
    """Distill a thread into a skill draft; set save=true to write immediately."""
    try:
        return await distill_skill(request, body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SkillNotEligibleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("skill distill failed for thread %s", body.thread_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/save", response_model=DistillSkillResponse)
async def save_skill_route(
    request: Request,
    body: SaveSkillRequest,
) -> DistillSkillResponse:
    """Persist a previewed skill draft to app/skills/."""
    try:
        return await save_skill(request, body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SkillNotEligibleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("skill save failed for thread %s", body.thread_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
