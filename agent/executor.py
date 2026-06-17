# app/agents/executor.py
import json
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from audit.logger import write_audit_event
from config.prompts import PROMPTS
from graph.schemas import ExecutorResult
from graph.state import AgentState, ToolCallRecord
from llm.providers import get_llm
from llm.retry import call_llm
from rag.config import load_rag_settings
from tools.registry import get_executor_tools, get_tool_by_name

MAX_TOOL_ITERATIONS = 5


def _tool_output_to_content(output: Any) -> str:
    """Serialize a tool return value to a ToolMessage content string."""
    if isinstance(output, str):
        return output
    if isinstance(output, (list, dict, int, float, bool)) or output is None:
        return json.dumps(output, default=str)
    return str(output)


async def _run_tool_loop(
    state: AgentState,
    trajectory: list[BaseMessage],
    records: list[ToolCallRecord],
) -> list[BaseMessage]:
    """Run a bounded tool-calling loop and return the working history.

    ``trajectory`` accumulates messages destined for the graph state via
    the ``add_messages`` reducer. ``records`` accumulates compact
    ToolCallRecords for the reviewer and the audit log.
    """
    llm = get_llm()
    tools = get_executor_tools()
    if tools:
        llm = get_llm().bind_tools(tools)

    prior_review = state.get("review")
    feedback = prior_review["reason"] if prior_review else "(none)"

    memory_prefix = ""
    rag_settings = load_rag_settings()
    if rag_settings.enabled and rag_settings.inject.executor:
        memory_prefix = f"{state.get('memory_context', '(no relevant memories)')}\n\n"

    history: list[BaseMessage] = [
        SystemMessage(content=PROMPTS["executor"]["system"].strip()),
        HumanMessage(
            content=(
                f"{memory_prefix}"
                f"Task: {state['task']}\n"
                f"Plan: {state['plan']}\n"
                f"Prior review feedback: {feedback}"
            )
        ),
    ]

    for iteration in range(MAX_TOOL_ITERATIONS):
        response: AIMessage = await call_llm(llm, history)
        trajectory.append(response)
        history.append(response)

        if not response.tool_calls:
            return history

        for call in response.tool_calls:
            name = call["name"]
            args = call.get("args", {}) or {}
            try:
                tool = get_tool_by_name(name)
                output = await tool.ainvoke(args)
                content = _tool_output_to_content(output)
                status = "ok"
            except Exception as exc:
                content = f"error: {exc}"
                status = "error"

            records.append(
                ToolCallRecord(
                    iteration=iteration,
                    tool=name,
                    args=args,
                    status=status,
                )
            )
            await write_audit_event(
                thread_id=state["thread_id"],
                round_number=state["rounds"] + 1,
                node="executor",
                event_type="tool_call",
                payload={
                    "iteration": iteration,
                    "tool": name,
                    "args": args,
                    "status": status,
                },
            )

            tool_msg = ToolMessage(content=content, tool_call_id=call["id"])
            trajectory.append(tool_msg)
            history.append(tool_msg)

    return history


async def executor_agent(state: AgentState) -> dict[str, object]:
    """Run a bounded tool-calling loop, then summarize as ExecutorResult.

    Phase 1: bind the executor tools and let the model call them until it
    stops asking for tools or hits ``MAX_TOOL_ITERATIONS``.

    Phase 2: pass the resulting trajectory to ``with_structured_output``
    to produce the typed ExecutorResult the reviewer consumes. ``bind_tools``
    and ``with_structured_output`` use the same underlying tool-calling
    mechanism, so the two phases must use separate model instances.
    """
    trajectory: list[BaseMessage] = []
    records: list[ToolCallRecord] = []
    history = await _run_tool_loop(state, trajectory, records)

    structured = get_llm().with_structured_output(ExecutorResult)
    execution: ExecutorResult = await call_llm(
        structured,
        history
        + [
            HumanMessage(
                content=PROMPTS["executor"]["summarize"].strip()
            )
        ],
    )

    return {
        "role": "executor",
        "execution": execution.model_dump(),
        "result": execution.summary,
        "tool_calls": records,
        "messages": trajectory
        + [AIMessage(content=f"Executor summary: {execution.summary}")],
    }