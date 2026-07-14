# app/graph/builder.py
from langgraph.graph import END, START, StateGraph

from agent.actioner import actioner_agent
from agent.executor import executor_agent
from agent.learner import learner_agent
from agent.planner import planner_agent
from graph.routing import route_after_action
from graph.state import AgentState

HITL_PAUSE_NODES: list[str] = [
    "planner",
    "executor",
    "learner",
]


def create_workflow() -> StateGraph:
    """Create the uncompiled LangGraph workflow."""
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_agent)
    graph.add_node("executor", executor_agent)
    graph.add_node("learner", learner_agent)
    graph.add_node("actioner", actioner_agent)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "learner")
    graph.add_edge("learner", "actioner")
    graph.add_conditional_edges(
        "actioner",
        route_after_action,
        {
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

    When ``human_in_the_loop`` is True, pause after planner, executor, and
    learner so a human can inspect state before the next node runs.
    """
    workflow = create_workflow()
    if human_in_the_loop:
        return workflow.compile(
            checkpointer=checkpointer,
            interrupt_after=HITL_PAUSE_NODES,
        )
    return workflow.compile(checkpointer=checkpointer)
