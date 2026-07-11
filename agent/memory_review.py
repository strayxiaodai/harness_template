"""Map HITL action-review resume payloads to approved memories."""

from __future__ import annotations

from typing import Any

MEMORY_TYPES = frozenset({"fact", "preference", "entity", "summary"})


def action_review_message(
    *,
    has_memories: bool,
    skill_preview_ready: bool,
) -> str:
    """Pick interrupt message copy from the design matrix.

    Args:
        has_memories: Whether pending memory candidates exist.
        skill_preview_ready: Whether the loop score qualifies for skill preview.

    Returns:
        Human-readable interrupt message for the action review panel.
    """
    if has_memories and skill_preview_ready:
        return (
            "Review memories before they are stored. "
            "Skill preview is available."
        )
    if has_memories:
        return "Review memories before they are stored."
    return (
        "Loop score qualifies for skill preview. "
        "Nothing to store this round."
    )


def map_resume_to_approved(
    pending: list[dict[str, Any]],
    resume_value: Any,
) -> list[dict[str, Any]]:
    """Apply keep/drop/edit rules from the action_review resume value.

    Args:
        pending: Pending memory candidates with stable ids.
        resume_value: Resume payload from the HITL interrupt.

    Returns:
        Approved memories without ids, ready for store commit.
    """
    if resume_value is True or resume_value is None:
        return [_strip_id(item) for item in pending]
    if not isinstance(resume_value, dict):
        return [_strip_id(item) for item in pending]
    if "memories" not in resume_value:
        return [_strip_id(item) for item in pending]

    raw_list = resume_value.get("memories")
    if not isinstance(raw_list, list):
        return [_strip_id(item) for item in pending]
    if len(raw_list) == 0:
        return []

    by_id = {
        str(row.get("id")): row
        for row in raw_list
        if isinstance(row, dict) and row.get("id") is not None
    }
    approved: list[dict[str, Any]] = []
    for item in pending:
        mid = str(item.get("id", ""))
        row = by_id.get(mid)
        if row is None or not row.get("keep"):
            continue
        content = str(row.get("content", item.get("content", ""))).strip()
        if not content:
            continue
        memory_type = str(row.get("memory_type", item.get("memory_type", "fact")))
        if memory_type not in MEMORY_TYPES:
            memory_type = str(item.get("memory_type", "fact"))
        try:
            importance = float(row.get("importance", item.get("importance", 0.5)))
        except (TypeError, ValueError):
            importance = float(item.get("importance", 0.5))
        importance = max(0.0, min(1.0, importance))
        approved.append(
            {
                "content": content,
                "memory_type": memory_type,
                "importance": importance,
            },
        )
    return approved


def _strip_id(item: dict[str, Any]) -> dict[str, Any]:
    """Return a pending memory dict without its stable id.

    Args:
        item: Pending memory candidate.

    Returns:
        Approved-memory-shaped dict.
    """
    return {
        "content": str(item.get("content", "")),
        "memory_type": str(item.get("memory_type", "fact")),
        "importance": float(item.get("importance", 0.5)),
    }
