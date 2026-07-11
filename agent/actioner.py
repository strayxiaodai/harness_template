# app/agents/actioner.py
"""Score loops, gather memory candidates, and pause for HITL action review."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from audit.logger import write_audit_event
from config.prompts import PROMPTS
from graph.schemas import ActionScoreResult
from graph.state import AgentState
from llm.providers import get_llm
from llm.retry import call_llm
from agent.memory_review import (
    action_review_message,
    clear_pending,
    load_pending,
    map_resume_to_approved,
    stash_pending,
)
from rag.ingest.memory_extract import extract_memory_candidates
from skills.eligibility import SKILL_PREVIEW_SCORE_THRESHOLD

logger = logging.getLogger(__name__)


def _heuristic_loop_score(state: AgentState) -> int:
    """Derive a loop score without calling the LLM."""
    review = state.get("review")
    execution = state.get("execution") or {}
    if review is None:
        return 0

    score = 45
    if review.get("verdict") == "pass":
        score += 35
    else:
        suggested = review.get("suggested_step", "executor")
        if suggested == "executor":
            score += 15
        elif suggested == "planner":
            score += 5

    verification = execution.get("verification") or []
    score += min(15, len(verification) * 5)

    risks = execution.get("risks") or []
    score -= min(20, len(risks) * 5)

    if execution.get("summary"):
        score += 5

    return max(0, min(100, score))


def _format_score_context(state: AgentState) -> str:
    """Build the actioner scoring prompt from harness state."""
    review = state.get("review") or {}
    execution = state.get("execution") or {}
    return (
        f"Task: {state['task']}\n"
        f"Plan: {state['plan']}\n"
        f"Round (before increment): {state['rounds']}\n"
        f"Approved: {state['approved']}\n"
        f"Review verdict: {review.get('verdict', '')}\n"
        f"Review reason: {review.get('reason', '')}\n"
        f"Suggested step: {review.get('suggested_step', '')}\n"
        f"Executor summary: {execution.get('summary', '')}\n"
        f"Changes: {execution.get('changes', [])}\n"
        f"Risks: {execution.get('risks', [])}\n"
        f"Verification: {execution.get('verification', [])}"
    )


async def score_loop(state: AgentState) -> ActionScoreResult:
    """Score loop quality with structured LLM output and heuristic fallback."""
    fallback_score = _heuristic_loop_score(state)
    fallback = ActionScoreResult(
        score=fallback_score,
        rationale="Heuristic score from review verdict and executor evidence.",
    )

    try:
        llm = get_llm().with_structured_output(ActionScoreResult)
        return await call_llm(
            llm,
            [
                SystemMessage(content=PROMPTS["actioner"]["system"].strip()),
                HumanMessage(content=_format_score_context(state)),
            ],
        )
    except Exception as exc:
        logger.warning("Actioner LLM scoring failed; using heuristic: %s", exc)
        return fallback


async def actioner_agent(state: AgentState) -> dict[str, object]:
    """Score the loop, optionally pause for HITL action review, then route.

    Human-in-the-loop runs pause when there are pending memory candidates or
    when the score reaches ``SKILL_PREVIEW_SCORE_THRESHOLD`` (80). The resume
    value decides which memories become approved for the memorize node to store.
    """
    review = state.get("review")
    suggestion = "finish" if review is None else review["suggested_step"]
    next_round = state["rounds"] + 1

    score_result = await score_loop(state)
    score = score_result.score
    skill_preview_ready = score >= SKILL_PREVIEW_SCORE_THRESHOLD

    thread_id = state["thread_id"]
    memory_cursor = state.get("memory_cursor")
    pending = state.get("pending_memories") or load_pending(
        thread_id,
        memory_cursor,
    )
    if pending is None:
        try:
            pending = await extract_memory_candidates(state)
        except Exception as exc:
            logger.warning("Actioner memory extraction failed; skipping: %s", exc)
            pending = []

    action_review_interrupted = bool(
        state.get("human_in_the_loop") and (pending or skill_preview_ready),
    )
    if action_review_interrupted:
        stash_pending(thread_id, memory_cursor, pending)
        resume_value = interrupt(
            {
                "kind": "action_review",
                "node": "actioner",
                "score": score,
                "threshold": SKILL_PREVIEW_SCORE_THRESHOLD,
                "skill_preview_ready": skill_preview_ready,
                "message": action_review_message(
                    has_memories=bool(pending),
                    skill_preview_ready=skill_preview_ready,
                ),
                "memories": pending,
            },
        )
        approved_memories = map_resume_to_approved(pending, resume_value)
    else:
        approved_memories = map_resume_to_approved(pending, True)
    clear_pending(thread_id, memory_cursor)

    await write_audit_event(
        thread_id=state["thread_id"],
        round_number=next_round,
        node="actioner",
        event_type="route_decision",
        payload={
            "suggested_step": suggestion,
            "approved": state["approved"],
            "loop_score": score,
            "skill_preview_ready": skill_preview_ready,
            "score_rationale": score_result.rationale,
            "pending_memory_count": len(pending),
            "approved_memory_count": len(approved_memories),
            "action_review_interrupted": action_review_interrupted,
        },
    )

    return {
        "role": "actioner",
        "rounds": next_round,
        "refine_from": suggestion,
        "loop_score": score,
        "skill_preview_ready": skill_preview_ready,
        "pending_memories": pending,
        "approved_memories": approved_memories,
    }
