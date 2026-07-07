# app/graph/builder.py
from langgraph.graph import END, START, StateGraph

from agent.actioner import actioner_agent
from agent.executor import executor_agent
from agent.memorize import memorize_agent
from agent.planner import planner_agent
from agent.reviewer import reviewer_agent
from graph.routing import route_after_action
from graph.state import AgentState

HITL_PAUSE_NODES: list[str] = [
    "planner",
    "executor",
    "reviewer",
    "memorize",
]


def create_workflow() -> StateGraph:
    """Create the uncompiled LangGraph workflow."""
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_agent)
    graph.add_node("executor", executor_agent)
    graph.add_node("reviewer", reviewer_agent)
    graph.add_node("actioner", actioner_agent)
    graph.add_node("memorize", memorize_agent)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "reviewer")
    graph.add_edge("reviewer", "actioner")
    graph.add_edge("actioner", "memorize")
    graph.add_conditional_edges(
        "memorize",
        route_after_action,
        {
            "executor": "executor",
            "planner": "planner",
            "finish": END,
        },
    )

    return graph


def compile_with_checkpointer(
    checkpointer: object,
    *,
    human_in_the_loop: bool = False,
) -> object:
    """Compile the workflow with a checkpointer.

    When ``human_in_the_loop`` is True, pause after every node so a human
    can inspect state before the next node runs.
    """
    workflow = create_workflow()
    if human_in_the_loop:
        return workflow.compile(
            checkpointer=checkpointer,
            interrupt_after=HITL_PAUSE_NODES,
        )
    return workflow.compile(checkpointer=checkpointer)
