# app/agents/learner.py
"""Learner agent: challenge executor output and capture lessons."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.services.thread_artifacts import lookup_thread_dir
from audit.logger import write_audit_event
from config.prompts import PROMPTS
from graph.schemas import LearningResult
from graph.state import AgentState, ToolCallRecord
from llm.providers import get_llm
from llm.retry import call_llm
from tools.manifest import load_manifest
from tools.registry import get_learner_tools

load_dotenv()

MAX_TOOL_ITERATIONS = 5


def _format_tool_calls(tool_calls: list[ToolCallRecord] | None) -> str:
    """Format compact tool call records for the learner prompt."""
    if not tool_calls:
        return "(none)"
    lines = []
    for record in tool_calls:
        lines.append(
            f"- iter {record['iteration']}: {record['tool']} "
            f"args={record['args']} status={record['status']}"
        )
    return "\n".join(lines)


def _format_manifest(thread_id: str) -> str:
    """List manifest entries for the learner prompt."""
    root = lookup_thread_dir(thread_id)
    if root is None:
        return "(no thread scripts dir)"
    entries = load_manifest(root / "scripts")
    if not entries:
        return "(none)"
    lines = [
        f"- {entry.path}: {entry.purpose or '(no purpose)'}"
        for entry in entries
    ]
    return "\n".join(lines)


def _tool_output_to_content(output: Any) -> str:
    """Serialize a tool return value to a ToolMessage content string."""
    if isinstance(output, str):
        return output
    if isinstance(output, (list, dict, int, float, bool)) or output is None:
        return json.dumps(output, default=str)
    return str(output)


def _parse_script_runs(records: list[ToolCallRecord], contents: list[str]) -> list[dict[str, object]]:
    """Extract compact script_runs from run_thread_script tool outputs."""
    runs: list[dict[str, object]] = []
    for record, content in zip(records, contents, strict=False):
        if record["tool"] != "run_thread_script" or record["status"] != "ok":
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            runs.append(payload)
    return runs


async def _run_tool_loop(
    state: AgentState,
    trajectory: list[BaseMessage],
    records: list[ToolCallRecord],
    tool_contents: list[str],
) -> list[BaseMessage]:
    """Bounded learner tool loop; returns history for structured summarize."""
    llm = get_llm()
    tools = get_learner_tools(state["thread_id"])
    tool_by_name = {tool.name: tool for tool in tools}
    if tools:
        llm = get_llm().bind_tools(tools)

    execution = state.get("execution") or {}
    history: list[BaseMessage] = [
        SystemMessage(content=PROMPTS["learner"]["system"].strip()),
        HumanMessage(
            content=(
                f"Task: {state['task']}\n"
                f"Plan: {state['plan']}\n"
                f"Executor summary: {execution.get('summary', '')}\n"
                f"Changes: {execution.get('changes', [])}\n"
                f"Risks: {execution.get('risks', [])}\n"
                f"Verification: {execution.get('verification', [])}\n"
                f"Executor tool calls:\n"
                f"{_format_tool_calls(state.get('tool_calls'))}\n"
                f"Runnable scripts (manifest):\n"
                f"{_format_manifest(state['thread_id'])}\n"
                "Use run_thread_script for relevant manifest entries when needed, "
                "then stop calling tools."
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
            tool_contents.append(content)
            await write_audit_event(
                thread_id=state["thread_id"],
                round_number=state["rounds"] + 1,
                node="learner",
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


async def learner_agent(state: AgentState) -> dict[str, object]:
    """Challenge the current result and return structured learning."""
    trajectory: list[BaseMessage] = []
    records: list[ToolCallRecord] = []
    tool_contents: list[str] = []
    history = await _run_tool_loop(state, trajectory, records, tool_contents)

    structured = get_llm().with_structured_output(LearningResult)
    learning: LearningResult = await call_llm(
        structured,
        history
        + [
            HumanMessage(
                content=(
                    "Now produce the LearningResult verdict using the evidence "
                    "above (including any script run outputs)."
                )
            )
        ],
    )

    script_runs = _parse_script_runs(records, tool_contents)
    return {
        "role": "learner",
        "approved": learning.verdict == "pass",
        "learning": {
            "verdict": learning.verdict,
            "reason": learning.reason,
            "suggested_step": learning.suggested_step,
            "lessons": learning.lessons.model_dump(),
        },
        "learning_candidates": [
            candidate.model_dump() for candidate in learning.learning_candidates
        ],
        "learner_tool_calls": records,
        "script_runs": script_runs,
        "messages": trajectory
        + [
            AIMessage(
                content=f"Learning {learning.verdict}: {learning.reason}"
            )
        ],
    }
