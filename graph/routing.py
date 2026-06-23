# app/graph/routing.py
from typing import Literal

from graph.state import AgentState

ActionRoute = Literal["executor", "planner", "finish"]

DEFAULT_MAX_ROUNDS = 3


def route_after_action(state: AgentState) -> ActionRoute:
    """Finish or refine after the memorize step."""
    if state.get("approved"):
        return "finish"

    if state["rounds"] >= state.get("max_rounds", DEFAULT_MAX_ROUNDS):
        return "finish"

    refine_from = state.get("refine_from", "executor")

    if refine_from == "planner":
        return "planner"

    if refine_from == "finish":
        return "finish"

    return "executor"
