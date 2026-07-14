"""Map LangGraph checkpoints to API responses."""

from __future__ import annotations

from typing import Any

from app.schemas.run import InterruptPayload, RunResponse
from skills.eligibility import thread_eligible_for_skill


def _interrupt_payload(snapshot: Any) -> InterruptPayload | None:
    """Build InterruptPayload from the first active snapshot interrupt."""
    interrupts = tuple(getattr(snapshot, "interrupts", None) or ())
    if not interrupts:
        return None
    raw = interrupts[0]
    return InterruptPayload(
        id=getattr(raw, "id", None),
        value=getattr(raw, "value", None),
    )


async def snapshot_to_response(graph: object, thread_id: str) -> RunResponse:
    """Translate the latest checkpoint into an API response."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await graph.aget_state(config)
    next_nodes = tuple(snapshot.next or ())
    values = snapshot.values or {}
    hitl = bool(values.get("human_in_the_loop", False))
    interrupts = tuple(getattr(snapshot, "interrupts", None) or ())
    needs_human = hitl and (bool(next_nodes) or bool(interrupts))
    skill_eligible, skill_ineligible_reason = thread_eligible_for_skill(values)

    return RunResponse(
        thread_id=thread_id,
        status="awaiting_human" if needs_human else "complete",
        approved=bool(values.get("approved", False)),
        needs_human=needs_human,
        result=values.get("result"),
        next_action=next_nodes[0] if next_nodes else (
            "actioner" if interrupts else None
        ),
        last_role=str(values.get("role", "")) or None,
        rounds=int(values.get("rounds", 0)),
        max_rounds=int(values.get("max_rounds", 0)),
        skill_eligible=skill_eligible,
        skill_ineligible_reason=skill_ineligible_reason or None,
        interrupt=_interrupt_payload(snapshot),
        plan=values.get("plan"),
        execution=values.get("execution"),
        tool_calls=values.get("tool_calls"),
        learning=values.get("learning"),
        learning_candidates=values.get("learning_candidates"),
        refine_from=values.get("refine_from"),
        loop_score=values.get("loop_score"),
        skill_preview_ready=values.get("skill_preview_ready"),
        memory_cursor=values.get("memory_cursor"),
    )
