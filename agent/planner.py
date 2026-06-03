# app/agents/planner.py
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config.prompts import PROMPTS
from graph.schemas import PlanResult
from graph.state import AgentState
from llm.providers import get_llm
from llm.retry import call_llm

load_dotenv()


async def planner_agent(state: AgentState) -> dict[str, object]:
    """Draft or revise the implementation plan."""
    llm = get_llm()
    structured = llm.with_structured_output(PlanResult)

    review = state.get("review")
    feedback = review["reason"] if review else "(none)"

    plan: PlanResult = await call_llm(
        structured,
        [
            SystemMessage(content=PROMPTS["planner"]["system"].strip()),
            HumanMessage(
                content=(
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
        "messages": [
            AIMessage(
                content=f"Plan rationale: {plan.rationale}\nSteps: {plan.steps}"
            )
        ],
    }
