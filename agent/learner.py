# app/agents/learner.py
"""Learner agent: challenge executor output and capture lessons."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config.prompts import PROMPTS
from graph.schemas import LearningResult
from graph.state import AgentState, ToolCallRecord
from llm.providers import get_llm
from llm.retry import call_llm

load_dotenv()


def _format_tool_calls(tool_calls: list[ToolCallRecord] | None) -> str:
    """Format compact tool call records for the learner prompt.

    Args:
        tool_calls: Executor tool call records from state.

    Returns:
        Human-readable summary for the LLM.
    """
    if not tool_calls:
        return "(none)"
    lines = []
    for record in tool_calls:
        lines.append(
            f"- iter {record['iteration']}: {record['tool']} "
            f"args={record['args']} status={record['status']}"
        )
    return "\n".join(lines)


async def learner_agent(state: AgentState) -> dict[str, object]:
    """Challenge the current result and return structured learning."""
    llm = get_llm()
    structured = llm.with_structured_output(LearningResult)
    execution = state.get("execution") or {}

    learning: LearningResult = await call_llm(
        structured,
        [
            SystemMessage(content=PROMPTS["learner"]["system"].strip()),
            HumanMessage(
                content=(
                    f"Task: {state['task']}\n"
                    f"Plan: {state['plan']}\n"
                    f"Executor summary: {execution.get('summary', '')}\n"
                    f"Changes: {execution.get('changes', [])}\n"
                    f"Risks: {execution.get('risks', [])}\n"
                    f"Verification: {execution.get('verification', [])}\n"
                    f"Tool calls:\n{_format_tool_calls(state.get('tool_calls'))}"
                )
            ),
        ],
    )

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
        "messages": [
            AIMessage(
                content=f"Learning {learning.verdict}: {learning.reason}"
            )
        ],
    }
