# app/graph/routing.py
from typing import Literal

from graph.state import AgentState

ActionRoute = Literal["planner", "finish"]

DEFAULT_MAX_ROUNDS = 3


def route_after_action(state: AgentState) -> ActionRoute:
    """Finish or continue at planner after the actioner step."""
    if state.get("approved"):
        return "finish"

    if state["rounds"] >= state.get("max_rounds", DEFAULT_MAX_ROUNDS):
        return "finish"

    refine_from = state.get("refine_from", "planner")
    if refine_from == "finish":
        return "finish"

    # planner, legacy executor, or unknown → planner
    return "planner"
