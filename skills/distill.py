"""Distill a harness thread checkpoint into a reusable Cursor skill."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config.prompts import PROMPTS
from llm.providers import get_llm
from llm.retry import call_llm
from skills.context import format_thread_context
from skills.eligibility import thread_eligible_for_skill
from skills.schemas import DistillSkillResponse, SkillDraft
from skills.store import normalize_slug, read_skill, skill_path, slugify, write_skill

logger = logging.getLogger(__name__)


class SkillNotEligibleError(ValueError):
    """Raised when a thread has not completed enough work to distill."""


def _require_skill_eligible(values: dict[str, object]) -> None:
    """Raise when the thread cannot yet be distilled into a skill."""
    eligible, reason = thread_eligible_for_skill(values)
    if not eligible:
        raise SkillNotEligibleError(reason)


def _resolve_slug(values: dict[str, Any], requested_name: str | None) -> str:
    if requested_name:
        return normalize_slug(requested_name)
    task = str(values.get("task", "")).strip()
    if task:
        return slugify(task)
    thread_id = str(values.get("thread_id", "harness-task"))
    return slugify(thread_id)


def _build_user_prompt(
    *,
    context: str,
    existing_name: str | None,
    existing_description: str | None,
    existing_body: str | None,
) -> str:
    if existing_body:
        return (
            "Refine the existing harness skill using a new completed thread.\n"
            "Preserve useful steps, merge duplicates, and improve clarity.\n\n"
            f"### Existing skill name\n{existing_name}\n\n"
            f"### Existing description\n{existing_description}\n\n"
            f"### Existing SKILL.md body\n{existing_body}\n\n"
            f"### New thread context\n{context}"
        )
    return (
        "Distill this completed harness thread into a reusable Cursor Agent Skill.\n"
        "Focus on durable workflow steps, conventions, pitfalls, and verification.\n"
        "Omit transient tool noise and one-off debugging.\n\n"
        f"### Thread context\n{context}"
    )


async def _draft_skill(
    *,
    context: str,
    existing_name: str | None = None,
    existing_description: str | None = None,
    existing_body: str | None = None,
) -> SkillDraft:
    llm = get_llm().with_structured_output(SkillDraft)
    return await call_llm(
        llm,
        [
            SystemMessage(content=PROMPTS["skills"]["distill"].strip()),
            HumanMessage(
                content=_build_user_prompt(
                    context=context,
                    existing_name=existing_name,
                    existing_description=existing_description,
                    existing_body=existing_body,
                ),
            ),
        ],
    )


async def distill_skill_from_thread(
    graph: object,
    *,
    thread_id: str,
    name: str | None = None,
    refine: bool = True,
    save: bool = False,
) -> DistillSkillResponse:
    """Read a thread checkpoint and optionally write a Cursor-compatible skill.

    Args:
        graph: Compiled LangGraph with the shared checkpointer.
        thread_id: Harness thread identifier.
        name: Optional slug override.
        refine: Merge with an existing on-disk skill when present.
        save: When False, return a preview without writing to disk.

    Returns:
        DistillSkillResponse with draft content and optional filesystem path.
    """
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await graph.aget_state(config)
    values = snapshot.values or {}
    if not values:
        msg = f"No checkpoint found for thread {thread_id}"
        raise LookupError(msg)

    _require_skill_eligible(values)

    slug = _resolve_slug(values, name)
    context = format_thread_context(values)

    existing_name: str | None = None
    existing_description: str | None = None
    existing_body: str | None = None
    created = True
    refined = False

    if skill_path(slug).is_file():
        if not refine:
            msg = f"Skill already exists at {slug}; set refine=true to merge"
            raise FileExistsError(msg)
        existing_name, existing_description, existing_body = read_skill(slug)
        created = False
        refined = True

    draft = await _draft_skill(
        context=context,
        existing_name=existing_name,
        existing_description=existing_description,
        existing_body=existing_body,
    )
    draft_slug = normalize_slug(draft.name)
    if name:
        draft_slug = slug
    elif draft_slug != slug:
        slug = draft_slug

    next_nodes = tuple(snapshot.next or ())
    status = "complete" if not next_nodes else "in_progress"

    path: str | None = None
    if save:
        written = write_skill(
            slug,
            name=draft.name,
            description=draft.description,
            body=draft.body,
            thread_id=thread_id,
            task=str(values.get("task", "")),
            rounds=int(values.get("rounds", 0)),
        )
        path = str(written)

    return DistillSkillResponse(
        thread_id=thread_id,
        slug=slug,
        path=path,
        saved=save,
        created=created if save else False,
        refined=refined if save else False,
        description=draft.description,
        name=draft.name,
        body=draft.body,
        status=status,
    )


async def save_skill_draft(
    graph: object,
    *,
    thread_id: str,
    slug: str,
    name: str,
    description: str,
    body: str,
) -> DistillSkillResponse:
    """Persist a previewed skill draft without re-running the LLM."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await graph.aget_state(config)
    values = snapshot.values or {}
    if not values:
        msg = f"No checkpoint found for thread {thread_id}"
        raise LookupError(msg)

    _require_skill_eligible(values)

    normalized_slug = normalize_slug(slug)
    created = not skill_path(normalized_slug).is_file()
    refined = not created

    written = write_skill(
        normalized_slug,
        name=name,
        description=description,
        body=body,
        thread_id=thread_id,
        task=str(values.get("task", "")),
        rounds=int(values.get("rounds", 0)),
    )

    next_nodes = tuple(snapshot.next or ())
    status = "complete" if not next_nodes else "in_progress"

    return DistillSkillResponse(
        thread_id=thread_id,
        slug=normalized_slug,
        path=str(written),
        saved=True,
        created=created,
        refined=refined,
        description=description,
        name=name,
        body=body,
        status=status,
    )
