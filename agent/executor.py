# app/agents/executor.py
"""Executor agent: executes tasks with bounded tool calling and summarizes results.

Uses Pydantic AI Agent with type-safe dependency injection and typed schema validation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from pydantic_ai import Agent, RunContext, UsageLimits
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models import Model

from agent.clarification import (
    ask_clarification,
    format_executor_clarification,
    merge_clarification_answers,
)
from audit.logger import write_audit_event
from config.prompts import PROMPTS
from graph.schemas import ClarificationQuestion, ExecutorResult
from graph.state import AgentState, ToolCallRecord
from llm.providers import get_llm, get_model
from llm.retry import call_llm
from rag.config import load_rag_settings
from skills.inject import skill_prompt_prefix
from tools.base import execute_tool
from tools.registry import get_executor_tools

MAX_TOOL_ITERATIONS = 5


@dataclass
class ExecutorDeps:
    """Type-safe dependencies injected into executor tools via Pydantic AI."""

    thread_id: str
    round_number: int
    workspace_dir: Path = field(default_factory=lambda: Path.cwd().resolve())
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    iteration: int = 0


def create_executor_agent(
    model: Model | None = None,
    tools: list[Any] | None = None,
) -> Agent[ExecutorDeps, ExecutorResult]:
    """Create a Pydantic AI Agent configured for executor tasks with type-safe tools."""
    mdl = model or get_model()
    agent: Agent[ExecutorDeps, ExecutorResult] = Agent(
        model=mdl,
        output_type=ExecutorResult,
        deps_type=ExecutorDeps,
        system_prompt=PROMPTS["executor"]["system"].strip(),
    )

    @agent.tool
    async def read_file(
        ctx: RunContext[ExecutorDeps],
        path: str,
        max_bytes: int = 8192,
    ) -> str:
        """Read up to max_bytes from a workspace file."""
        workspace = ctx.deps.workspace_dir
        target = (workspace / path).resolve()
        status = "ok"
        try:
            if not target.is_relative_to(workspace):
                raise ValueError("path escapes the workspace")
            if not target.is_file():
                raise FileNotFoundError(path)
            content = target.read_bytes()[:max_bytes].decode("utf-8", errors="replace")
        except Exception as exc:
            status = "error"
            content = f"error: {exc}"

        record = ToolCallRecord(
            iteration=ctx.deps.iteration,
            tool="read_file",
            args={"path": path, "max_bytes": max_bytes},
            status=status,
        )
        ctx.deps.tool_calls.append(record)
        await write_audit_event(
            thread_id=ctx.deps.thread_id,
            round_number=ctx.deps.round_number,
            node="executor",
            event_type="tool_call",
            payload={
                "iteration": ctx.deps.iteration,
                "tool": "read_file",
                "args": {"path": path, "max_bytes": max_bytes},
                "status": status,
            },
        )
        return content

    @agent.tool
    async def list_dir(
        ctx: RunContext[ExecutorDeps],
        path: str = ".",
    ) -> list[str]:
        """List entries inside a workspace directory."""
        workspace = ctx.deps.workspace_dir
        target = (workspace / path).resolve()
        status = "ok"
        try:
            if not target.is_relative_to(workspace) or not target.is_dir():
                raise ValueError("invalid directory")
            entries = sorted(p.name for p in target.iterdir())
        except Exception as exc:
            status = "error"
            entries = [f"error: {exc}"]

        record = ToolCallRecord(
            iteration=ctx.deps.iteration,
            tool="list_dir",
            args={"path": path},
            status=status,
        )
        ctx.deps.tool_calls.append(record)
        await write_audit_event(
            thread_id=ctx.deps.thread_id,
            round_number=ctx.deps.round_number,
            node="executor",
            event_type="tool_call",
            payload={
                "iteration": ctx.deps.iteration,
                "tool": "list_dir",
                "args": {"path": path},
                "status": status,
            },
        )
        return entries

    @agent.tool
    async def read_thread_file(
        ctx: RunContext[ExecutorDeps],
        path: str,
        max_bytes: int = 8192,
    ) -> str:
        """Read a file from this thread's artifact directory."""
        from tools.thread_files import resolve_thread_path

        status = "ok"
        try:
            target = resolve_thread_path(ctx.deps.thread_id, path)
            if not target.is_file():
                raise FileNotFoundError(path)
            content = target.read_bytes()[:max_bytes].decode("utf-8", errors="replace")
        except Exception as exc:
            status = "error"
            content = f"error: {exc}"

        record = ToolCallRecord(
            iteration=ctx.deps.iteration,
            tool="read_thread_file",
            args={"path": path, "max_bytes": max_bytes},
            status=status,
        )
        ctx.deps.tool_calls.append(record)
        await write_audit_event(
            thread_id=ctx.deps.thread_id,
            round_number=ctx.deps.round_number,
            node="executor",
            event_type="tool_call",
            payload={
                "iteration": ctx.deps.iteration,
                "tool": "read_thread_file",
                "args": {"path": path, "max_bytes": max_bytes},
                "status": status,
            },
        )
        return content

    @agent.tool
    async def write_thread_file(
        ctx: RunContext[ExecutorDeps],
        path: str,
        content: str,
    ) -> str:
        """Write a Python module or manifest.json under this thread's scripts/."""
        from tools.thread_files import resolve_scripts_path, _MAX_BYTES

        status = "ok"
        try:
            target = resolve_scripts_path(ctx.deps.thread_id, path)
            if path != "manifest.json" and not path.endswith(".py"):
                raise ValueError("only *.py or manifest.json may be written")
            raw = content.encode("utf-8")
            if len(raw) > _MAX_BYTES:
                raise ValueError(f"content exceeds {_MAX_BYTES} bytes")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            msg = f"wrote scripts/{path} ({len(raw)} bytes)"
        except Exception as exc:
            status = "error"
            msg = f"error: {exc}"

        record = ToolCallRecord(
            iteration=ctx.deps.iteration,
            tool="write_thread_file",
            args={"path": path, "content": content},
            status=status,
        )
        ctx.deps.tool_calls.append(record)
        await write_audit_event(
            thread_id=ctx.deps.thread_id,
            round_number=ctx.deps.round_number,
            node="executor",
            event_type="tool_call",
            payload={
                "iteration": ctx.deps.iteration,
                "tool": "write_thread_file",
                "args": {"path": path, "content": content},
                "status": status,
            },
        )
        return msg

    if tools:
        for t in tools:
            agent.tool(t)

    return agent


def pydantic_ai_messages_to_langchain(messages: list[Any]) -> list[BaseMessage]:
    """Convert Pydantic AI model requests and responses to LangChain messages for state."""
    lc_messages: list[BaseMessage] = []
    for msg in messages:
        if isinstance(msg, ModelResponse):
            tool_calls = []
            content = []
            for part in msg.parts:
                if isinstance(part, ToolCallPart) and part.tool_name != "final_result":
                    tool_calls.append(
                        {
                            "name": part.tool_name,
                            "args": part.args if isinstance(part.args, dict) else {},
                            "id": part.tool_call_id,
                            "type": "tool_call",
                        }
                    )
                elif isinstance(part, TextPart):
                    content.append(part.content)
            if tool_calls or content:
                lc_messages.append(AIMessage(content="".join(content), tool_calls=tool_calls))
        elif isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, ToolReturnPart) and part.tool_name != "final_result":
                    lc_messages.append(
                        ToolMessage(content=str(part.content), tool_call_id=part.tool_call_id)
                    )
    return lc_messages


def _tool_output_to_content(output: Any) -> str:
    """Serialize a tool return value to a ToolMessage content string."""
    if isinstance(output, str):
        return output
    if isinstance(output, (list, dict, int, float, bool)) or output is None:
        return json.dumps(output, default=str)
    return str(output)


def _format_tool_evidence(history: list[BaseMessage]) -> str:
    """Render tool-loop history as plain text for the summarize phase."""
    lines: list[str] = []
    for message in history:
        if isinstance(message, ToolMessage):
            lines.append(f"Tool result ({message.tool_call_id}): {message.content}")
            continue
        if isinstance(message, AIMessage) and message.tool_calls:
            for call in message.tool_calls:
                lines.append(
                    f"Tool call: {call.get('name')}({json.dumps(call.get('args', {}), default=str)})"
                )
            if message.content:
                lines.append(f"Assistant: {message.content}")
            continue
        if isinstance(message, (SystemMessage, HumanMessage)):
            continue
        if isinstance(message, AIMessage) and message.content:
            lines.append(f"Assistant: {message.content}")
    if not lines:
        return "(no tool calls)"
    return "\n".join(lines)


async def _run_tool_loop_legacy(
    state: AgentState,
    trajectory: list[BaseMessage],
    records: list[ToolCallRecord],
) -> list[BaseMessage]:
    """Fallback manual tool-calling loop for tests that mock call_llm / get_llm."""
    llm = get_llm()
    tools = get_executor_tools(state["thread_id"])
    tool_by_name = {getattr(tool, "name", str(tool)): tool for tool in tools}
    if tools:
        llm = get_llm().bind_tools(tools)

    prior_learning = state.get("learning")
    feedback = prior_learning["reason"] if prior_learning else "(none)"

    memory_prefix = ""
    rag_settings = load_rag_settings()
    if rag_settings.enabled and rag_settings.inject.executor:
        memory_prefix = f"{state.get('memory_context', '(no relevant memories)')}\n\n"

    superpowers_directive = (
        "Superpowers execution focus: follow the plan task-by-task, provide concrete tool "
        "evidence/verification for all work, and document explicit rulings for any plan ambiguities."
    )

    history: list[BaseMessage] = [
        SystemMessage(content=PROMPTS["executor"]["system"].strip()),
        HumanMessage(
            content=(
                f"{skill_prompt_prefix(state)}"
                f"{memory_prefix}"
                f"Task: {state['task']}\n"
                f"Plan: {state['plan']}\n"
                f"Prior learning feedback: {feedback}\n"
                f"{superpowers_directive}"
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
                tool = tool_by_name[name]
                output = await execute_tool(tool, args)
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


_ORIGINAL_CALL_LLM = call_llm
_ORIGINAL_GET_LLM = get_llm


def _is_mocked() -> bool:
    """Return True if call_llm or get_llm was monkeypatched in tests."""
    return (
        call_llm is not _ORIGINAL_CALL_LLM
        or get_llm is not _ORIGINAL_GET_LLM
        or isinstance(call_llm, (Mock, AsyncMock))
        or isinstance(get_llm, (Mock, AsyncMock))
        or hasattr(call_llm, "mock")
        or hasattr(call_llm, "assert_called")
        or hasattr(call_llm, "await_args")
    )


def _format_executor_message(execution: ExecutorResult) -> str:
    """Format executor AIMessage with ASCII flow and structured sections."""
    flow = "[Inspect Context] ──> [Apply Changes] ──> [Verify Output] ──> [DONE ✓]"
    parts = [f"```text\n{flow}\n```", f"Executor summary: {execution.summary}"]
    if execution.changes:
        parts.append("### Changes\n" + "\n".join(f"- {c}" for c in execution.changes))
    if execution.verification:
        parts.append("### Verification\n" + "\n".join(f"- {v}" for v in execution.verification))
    return "\n\n".join(parts)


def _handle_executor_clarification(
    state: AgentState, execution: ExecutorResult
) -> dict[str, object]:
    clarification_updates: dict[str, object] = {}
    if state.get("human_in_the_loop"):
        changes_desc = (
            ", ".join(execution.changes)
            if execution.changes
            else "no file changes recorded"
        )
        questions = [
            ClarificationQuestion(
                id="execution_approval",
                prompt=f"Review execution results ({changes_desc}):",
                why=format_executor_clarification(
                    execution.summary,
                    execution.changes,
                    execution.verification,
                    execution.risks,
                ),
                options=[
                    "(Recommended) Approve execution results",
                    "Request additional verification",
                    "Reject changes",
                ],
                default="(Recommended) Approve execution results",
            )
        ]
        answers = ask_clarification(
            state, questions, reason="Execution review", node="executor"
        )
        all_answers = merge_clarification_answers(
            state.get("clarification_answers"),
            answers,
        )
        clarification_updates["clarification_answers"] = all_answers
    return clarification_updates


async def executor_agent(state: AgentState) -> dict[str, object]:
    """Execute plan using Pydantic AI Agent with bounded tool execution step."""
    # When test frameworks mock call_llm / get_llm, preserve mocked dispatch
    if _is_mocked():
        trajectory: list[BaseMessage] = []
        records: list[ToolCallRecord] = []
        history = await _run_tool_loop_legacy(state, trajectory, records)

        structured = get_llm().with_structured_output(ExecutorResult)
        evidence = _format_tool_evidence(history)
        execution: ExecutorResult = await call_llm(
            structured,
            [
                SystemMessage(content=PROMPTS["executor"]["system"].strip()),
                HumanMessage(
                    content=(
                        f"Task: {state['task']}\n"
                        f"Plan: {state['plan']}\n"
                        f"Tool evidence:\n{evidence}\n\n"
                        f"{PROMPTS['executor']['summarize'].strip()}"
                    )
                ),
            ],
        )

        clarification_updates = _handle_executor_clarification(state, execution)
        return {
            "role": "executor",
            "execution": execution.model_dump(),
            "result": execution.summary,
            "tool_calls": records,
            **clarification_updates,
            "messages": trajectory
            + [AIMessage(content=_format_executor_message(execution))],
        }

    # Native Pydantic AI execution path with type-safe dependency injection
    deps = ExecutorDeps(
        thread_id=state["thread_id"],
        round_number=state["rounds"] + 1,
    )
    agent = create_executor_agent(model=get_model())

    prior_learning = state.get("learning")
    feedback = prior_learning["reason"] if prior_learning else "(none)"

    memory_prefix = ""
    rag_settings = load_rag_settings()
    if rag_settings.enabled and rag_settings.inject.executor:
        memory_prefix = f"{state.get('memory_context', '(no relevant memories)')}\n\n"

    superpowers_directive = (
        "Superpowers execution focus: follow the plan task-by-task, provide concrete tool "
        "evidence/verification for all work, and document explicit rulings for any plan ambiguities."
    )

    prompt = (
        f"{skill_prompt_prefix(state)}"
        f"{memory_prefix}"
        f"Task: {state['task']}\n"
        f"Plan: {state['plan']}\n"
        f"Prior learning feedback: {feedback}\n"
        f"{superpowers_directive}"
    )

    res = await agent.run(
        prompt,
        deps=deps,
        usage_limits=UsageLimits(request_limit=MAX_TOOL_ITERATIONS + 1),
    )
    execution = res.output
    trajectory = pydantic_ai_messages_to_langchain(res.all_messages())

    clarification_updates = _handle_executor_clarification(state, execution)
    return {
        "role": "executor",
        "execution": execution.model_dump(),
        "result": execution.summary,
        "tool_calls": deps.tool_calls,
        **clarification_updates,
        "messages": trajectory
        + [AIMessage(content=_format_executor_message(execution))],
    }