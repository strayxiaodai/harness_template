# app/agents/planner.py
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.clarification import (
    ask_clarification,
    format_ascii_pipeline,
    format_planner_clarification,
    merge_clarification_answers,
)
from config.prompts import PROMPTS
from context.pipeline import assemble_context
from graph.schemas import ClarificationQuestion, PlanResult
from graph.state import AgentState
from llm.providers import get_llm
from llm.retry import call_llm
from rag.config import load_rag_settings
from skills.inject import skill_prompt_prefix

load_dotenv()


async def planner_agent(state: AgentState) -> dict[str, object]:
    """Draft or revise the implementation plan using an OpenSpec explore stance.

    Acts as an exploratory thinking partner: maps existing architecture and
    constraints, surfaces assumptions, evaluates trade-offs in rationale, and
    decomposes work into verifiable steps with clear done-when outcomes.
    """
    llm = get_llm()
    structured = llm.with_structured_output(PlanResult)

    learning = state.get("learning")
    feedback = learning["reason"] if learning else "(none)"

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

    explore_directive = (
        "OpenSpec Explore focus: understand context, surface unverified assumptions, "
        "weigh trade-offs in rationale, and define verifiable done-when criteria for each step."
    )

    plan: PlanResult = await call_llm(
        structured,
        [
            SystemMessage(content=PROMPTS["planner"]["system"].strip()),
            HumanMessage(
                content=(
                    f"{skill_prompt_prefix(state)}"
                    f"{memory_block}"
                    f"Task: {state['task']}\n"
                    f"Current plan: {state['plan']}\n"
                    f"Prior learning feedback: {feedback}\n"
                    f"{explore_directive}"
                )
            ),
        ],
    )

    clarification_updates: dict[str, object] = {}
    if state.get("human_in_the_loop"):
        step_count = len(plan.steps)
        questions = [
            ClarificationQuestion(
                id="plan_approval",
                prompt=f"Confirm implementation plan ({step_count} steps):",
                why=format_planner_clarification(plan.steps, plan.rationale),
                options=[
                    f"(Recommended) Approve {step_count} planned steps",
                    "Require reproduction test case first",
                    "Abort and refine goal",
                ],
                default=f"(Recommended) Approve {step_count} planned steps",
            )
        ]
        answers = ask_clarification(
            state, questions, reason="Plan review", node="planner"
        )
        for ans in answers:
            if "reproduction test" in ans.get("answer", "").lower():
                plan.steps.insert(0, "Create minimal reproduction test case")
        all_answers = merge_clarification_answers(
            state.get("clarification_answers"),
            answers,
        )
        clarification_updates["clarification_answers"] = all_answers

    steps_display = "\n".join(f"{i}. {s}" for i, s in enumerate(plan.steps, 1))
    flow = format_ascii_pipeline(plan.steps)
    flow_prefix = f"```text\n{flow}\n```\n\n" if flow else ""
    return {
        "role": "planner",
        "plan": plan.steps,
        **memory_updates,
        **clarification_updates,
        "messages": [
            AIMessage(
                content=f"{flow_prefix}Plan rationale:\n{plan.rationale}\n\nSteps:\n{steps_display}"
            )
        ],
    }
