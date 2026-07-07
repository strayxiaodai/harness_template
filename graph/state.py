# app/graph/state.py
from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ExecutionRecord(TypedDict):
    """Serialized form of an ExecutorResult stored in state."""

    summary: str
    changes: list[str]
    risks: list[str]
    verification: list[str]


class ReviewRecord(TypedDict):
    """Serialized form of a ReviewResult stored in the graph state."""

    verdict: str
    reason: str
    suggested_step: str


class ToolCallRecord(TypedDict):
    """Compact record of one tool call made by the executor."""

    iteration: int
    tool: str
    args: dict[str, object]
    status: str


class AgentState(TypedDict):
    """Shared state passed between LangGraph nodes.

    ``thread_id`` is intentionally duplicated from the LangGraph runtime
    config (``config["configurable"]["thread_id"]``). Nodes receive the
    state but not the config, so storing the id here lets audit logging
    and prompt construction reference it without threading the config
    through every helper.
    """

    thread_id: str
    task: str
    messages: Annotated[list[BaseMessage], add_messages]
    plan: list[str]
    rounds: int
    max_rounds: int
    role: str
    result: NotRequired[str]
    execution: NotRequired[ExecutionRecord]
    approved: bool
    review: NotRequired[ReviewRecord]
    refine_from: NotRequired[str]
    tool_calls: NotRequired[list[ToolCallRecord]]
    human_in_the_loop: bool
    memory_cursor: NotRequired[int]
    memory_context: NotRequired[str]
    memory_context_round: NotRequired[int]
    skill_slug: NotRequired[str]
    skill_context: NotRequired[str]
    loop_score: NotRequired[int]
    skill_preview_ready: NotRequired[bool]