"""Map LangGraph checkpoints to API responses."""

from __future__ import annotations

from app.schemas.run import RunResponse
from skills.eligibility import thread_eligible_for_skill


async def snapshot_to_response(graph: object, thread_id: str) -> RunResponse:
    """Translate the latest checkpoint into an API response."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await graph.aget_state(config)
    next_nodes = tuple(snapshot.next or ())
    values = snapshot.values or {}
    hitl = bool(values.get("human_in_the_loop", False))
    needs_human = hitl and bool(next_nodes)
    skill_eligible, skill_ineligible_reason = thread_eligible_for_skill(values)

    return RunResponse(
        thread_id=thread_id,
        status="awaiting_human" if needs_human else "complete",
        approved=bool(values.get("approved", False)),
        needs_human=needs_human,
        result=values.get("result"),
        next_action=next_nodes[0] if next_nodes else None,
        last_role=str(values.get("role", "")) or None,
        rounds=int(values.get("rounds", 0)),
        max_rounds=int(values.get("max_rounds", 0)),
        skill_eligible=skill_eligible,
        skill_ineligible_reason=skill_ineligible_reason or None,
    )
