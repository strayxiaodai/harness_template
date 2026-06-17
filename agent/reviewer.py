# app/agents/reviewer.py
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config.prompts import PROMPTS
from graph.schemas import ReviewResult
from graph.state import AgentState, ToolCallRecord
from llm.providers import get_llm
from llm.retry import call_llm

load_dotenv()


def _format_tool_calls(tool_calls: list[ToolCallRecord] | None) -> str:
    """Format compact tool call records for the reviewer prompt.

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


async def reviewer_agent(state: AgentState) -> dict[str, object]:
    """Check the current result and return a structured verdict."""
    llm = get_llm()
    structured = llm.with_structured_output(ReviewResult)
    execution = state.get("execution") or {}

    review: ReviewResult = await call_llm(
        structured,
        [
            SystemMessage(content=PROMPTS["reviewer"]["system"].strip()),
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
        "role": "reviewer",
        "approved": review.verdict == "pass",
        "review": review.model_dump(),
        "messages": [
            AIMessage(content=f"Review {review.verdict}: {review.reason}")
        ],
    }
