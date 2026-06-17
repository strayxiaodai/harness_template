# app/agents/actioner.py
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from audit.logger import write_audit_event
from graph.state import AgentState


async def actioner_agent(state: AgentState) -> dict[str, object]:
    """Decide where the refinement loop should resume.

    The actioner does not redo the work. It increments the round counter,
    reads the reviewer's structured suggestion, and updates ``refine_from``.
    Routing is then driven by ``route_after_action``.
    """
    review = state.get("review")
    suggestion = "finish" if review is None else review["suggested_step"]
    next_round = state["rounds"] + 1

    await write_audit_event(
        thread_id=state["thread_id"],
        round_number=next_round,
        node="actioner",
        event_type="route_decision",
        payload={"suggested_step": suggestion, "approved": state["approved"]},
    )

    return {
        "role": "actioner",
        "rounds": next_round,
        "refine_from": suggestion,
    }
