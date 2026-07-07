"""Business logic for the harness skill library API."""

from __future__ import annotations

from fastapi import Request

from app.db.graphs import graph_for_checkpoint
from app.schemas.skills import (
    DistillSkillRequest,
    DistillSkillResponse,
    SaveSkillRequest,
    SkillDetail,
    SkillSummary,
)
from skills.distill import distill_skill_from_thread, save_skill_draft
from skills.store import list_skills, normalize_slug, read_meta, read_skill, skill_path


def list_skill_summaries() -> list[SkillSummary]:
    """List distilled skills in the library."""
    return [
        SkillSummary(
            slug=item.slug,
            name=item.name,
            description=item.description,
            path=item.path,
            thread_count=item.thread_count,
            updated_at=item.updated_at.isoformat() if item.updated_at else None,
        )
        for item in list_skills()
    ]


def get_skill_detail(slug: str) -> SkillDetail:
    """Return a saved skill playbook."""
    normalized = normalize_slug(slug)
    name, description, body = read_skill(normalized)
    meta = read_meta(normalized)
    updated_at = meta.distilled_at[-1] if meta.distilled_at else None
    return SkillDetail(
        slug=normalized,
        name=name,
        description=description,
        path=str(skill_path(normalized)),
        body=body,
        thread_count=len(meta.thread_ids),
        updated_at=updated_at,
    )


async def distill_skill(
    request: Request,
    body: DistillSkillRequest,
) -> DistillSkillResponse:
    """Distill a thread into a skill draft."""
    graph = graph_for_checkpoint(request)
    config: dict[str, object] = {"configurable": {"thread_id": body.thread_id}}
    snapshot = await graph.aget_state(config)
    values = snapshot.values or {}
    graph = graph_for_checkpoint(request, values=values)

    result = await distill_skill_from_thread(
        graph,
        thread_id=body.thread_id,
        name=body.name,
        refine=body.refine,
        save=body.save,
    )
    return map_distill_response(result)


async def save_skill(
    request: Request,
    body: SaveSkillRequest,
) -> DistillSkillResponse:
    """Persist a previewed skill draft."""
    graph = graph_for_checkpoint(request)
    config: dict[str, object] = {"configurable": {"thread_id": body.thread_id}}
    snapshot = await graph.aget_state(config)
    values = snapshot.values or {}
    graph = graph_for_checkpoint(request, values=values)

    result = await save_skill_draft(
        graph,
        thread_id=body.thread_id,
        slug=body.slug,
        name=body.name,
        description=body.description,
        body=body.body,
    )
    return map_distill_response(result)


def map_distill_response(result: object) -> DistillSkillResponse:
    """Map internal distill result to API response."""
    from skills.schemas import DistillSkillResponse as InternalResponse

    internal = InternalResponse.model_validate(result)
    return DistillSkillResponse(
        thread_id=internal.thread_id,
        slug=internal.slug,
        path=internal.path,
        saved=internal.saved,
        created=internal.created,
        refined=internal.refined,
        description=internal.description,
        name=internal.name,
        body=internal.body,
        status=internal.status,
    )
