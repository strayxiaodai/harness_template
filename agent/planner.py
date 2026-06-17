# app/agents/planner.py
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config.prompts import PROMPTS
from context.pipeline import assemble_context
from graph.schemas import PlanResult
from graph.state import AgentState
from llm.providers import get_llm
from llm.retry import call_llm
from rag.config import load_rag_settings

load_dotenv()


async def planner_agent(state: AgentState) -> dict[str, object]:
    """Draft or revise the implementation plan."""
    llm = get_llm()
    structured = llm.with_structured_output(PlanResult)

    review = state.get("review")
    feedback = review["reason"] if review else "(none)"

    memory_block = ""
    memory_updates: dict[str, object] = {}
    rag_settings = load_rag_settings()
    if rag_settings.enabled and rag_settings.inject.planner:
        ctx = await assemble_context(state)
        memory_block = f"{ctx.memory_block}\n\n"
        memory_updates = {
            "memory_context": ctx.memory_block,
            "memory_context_round": state["rounds"],
        }

    plan: PlanResult = await call_llm(
        structured,
        [
            SystemMessage(content=PROMPTS["planner"]["system"].strip()),
            HumanMessage(
                content=(
                    f"{memory_block}"
                    f"Task: {state['task']}\n"
                    f"Current plan: {state['plan']}\n"
                    f"Prior review feedback: {feedback}"
                )
            ),
        ],
    )

    return {
        "role": "planner",
        "plan": plan.steps,
        **memory_updates,
        "messages": [
            AIMessage(
                content=f"Plan rationale: {plan.rationale}\nSteps: {plan.steps}"
            )
        ],
    }
