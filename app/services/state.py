"""Build initial LangGraph state from API run requests."""

from __future__ import annotations

import logging

from app.schemas.run import RunRequest
from skills.store import normalize_slug, read_skill

logger = logging.getLogger(__name__)


def initial_state(request: RunRequest) -> dict[str, object]:
    """Build the starting graph state for a new thread."""
    task = request.task.strip()
    state: dict[str, object] = {
        "thread_id": request.thread_id,
        "task": task,
        "messages": [],
        "plan": request.plan,
        "rounds": 0,
        "max_rounds": request.max_rounds,
        "role": "",
        "approved": False,
        "human_in_the_loop": request.human_in_the_loop,
    }

    if request.skill_slug:
        slug = normalize_slug(request.skill_slug)
        name, description, body = read_skill(slug)
        if not task:
            task = f"Apply skill: {description}"
            state["task"] = task
        state["skill_slug"] = slug
        state["skill_context"] = body
        logger.info(
            "Loaded harness skill %s (%s) for thread %s",
            slug,
            name,
            request.thread_id,
        )

    return state
