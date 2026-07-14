# app/graph/routing.py
from typing import Literal

from graph.state import AgentState

ActionRoute = Literal["planner", "finish"]

DEFAULT_MAX_ROUNDS = 3


def learning_passed(state: AgentState) -> bool:
    """Return whether the latest learning verdict says pass.

    Prefer ``learning.verdict`` when present so HITL learning overrides stay
    consistent even if the top-level ``approved`` bit lags. Fall back to
    ``approved`` when learning is missing (legacy / sparse state).
    """
    learning = state.get("learning") or {}
    verdict = learning.get("verdict")
    if verdict == "pass":
        return True
    if verdict == "fail":
        return False
    return bool(state.get("approved"))


def route_after_action(state: AgentState) -> ActionRoute:
    """Finish or continue at planner after the actioner step."""
    if learning_passed(state):
        return "finish"

    if state["rounds"] >= state.get("max_rounds", DEFAULT_MAX_ROUNDS):
        return "finish"

    refine_from = state.get("refine_from", "planner")
    if refine_from == "finish":
        return "finish"

    # planner, legacy executor, or unknown → planner
    return "planner"
