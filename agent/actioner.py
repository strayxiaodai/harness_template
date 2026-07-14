# app/agents/actioner.py
"""Score loops, gather memory candidates, HITL review, and commit memories."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from agent.memorize import commit_round_memories
from agent.memory_review import (
    action_review_message,
    clear_pending,
    load_pending,
    map_resume_to_approved,
    stash_pending,
)
from audit.logger import write_audit_event
from config.prompts import PROMPTS
from graph.schemas import ActionScoreResult
from graph.state import AgentState
from llm.providers import get_llm
from llm.retry import call_llm
from rag.ingest.memory_extract import extract_memory_candidates
from skills.eligibility import SKILL_PREVIEW_SCORE_THRESHOLD

logger = logging.getLogger(__name__)


def _normalize_step(step: str | None) -> str:
    """Map refine/suggested steps to planner or finish."""
    if step == "finish":
        return "finish"
    return "planner"


def merge_learning_and_extract(
    learning_candidates: list[dict[str, object]] | None,
    extracted: list[dict[str, object]] | None,
) -> list[dict[str, object]]:
    """Dedupe by normalized content and assign stable ids m0.."""
    merged: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in list(learning_candidates or []) + list(extracted or []):
        content = str(row.get("content", "")).strip()
        key = " ".join(content.lower().split())
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(
            {
                "id": f"m{len(merged)}",
                "content": content,
                "memory_type": row.get("memory_type", "fact"),
                "importance": row.get("importance", 0.5),
            }
        )
    return merged


def _heuristic_loop_score(state: AgentState) -> int:
    """Derive a loop score without calling the LLM."""
    learning = state.get("learning")
    execution = state.get("execution") or {}
    if learning is None:
        return 0

    score = 45
    if learning.get("verdict") == "pass":
        score += 35
    else:
        suggested = learning.get("suggested_step", "planner")
        if suggested == "planner":
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
    learning = state.get("learning") or {}
    lessons = learning.get("lessons") or {}
    execution = state.get("execution") or {}
    return (
        f"Task: {state['task']}\n"
        f"Plan: {state['plan']}\n"
        f"Round (before increment): {state['rounds']}\n"
        f"Approved: {state['approved']}\n"
        f"Learning verdict: {learning.get('verdict', '')}\n"
        f"Learning reason: {learning.get('reason', '')}\n"
        f"Suggested step: {learning.get('suggested_step', '')}\n"
        f"Lessons worked: {lessons.get('worked', [])}\n"
        f"Lessons failed: {lessons.get('failed', [])}\n"
        f"Lessons risks: {lessons.get('risks', [])}\n"
        f"Lessons next_time: {lessons.get('next_time', [])}\n"
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
        rationale="Heuristic score from learning verdict and executor evidence.",
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
    """Soft-skip on fail; on pass score, HITL, and commit memories.

    Human-in-the-loop runs pause when there are pending memory candidates or
    when the score reaches ``SKILL_PREVIEW_SCORE_THRESHOLD`` (80). Resume
    decides which memories become approved before commit.
    """
    learning = state.get("learning") or {}
    suggestion = _normalize_step(
        learning.get("suggested_step")
        or ("finish" if state.get("approved") else "planner")
    )
    next_round = state["rounds"] + 1

    if not state.get("approved"):
        await write_audit_event(
            thread_id=state["thread_id"],
            round_number=next_round,
            node="actioner",
            event_type="route_decision",
            payload={
                "suggested_step": suggestion,
                "approved": False,
                "loop_score": 0,
                "skill_preview_ready": False,
                "soft_skip": True,
                "action_review_interrupted": False,
            },
        )
        return {
            "role": "actioner",
            "rounds": next_round,
            "refine_from": suggestion,
            "loop_score": 0,
            "skill_preview_ready": False,
        }

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
            extracted = await extract_memory_candidates(state)
        except Exception as exc:
            logger.warning("Actioner memory extraction failed; skipping: %s", exc)
            extracted = []
        pending = merge_learning_and_extract(
            list(state.get("learning_candidates") or []),
            extracted,
        )

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

    commit_state = {
        **state,
        "pending_memories": pending,
        "approved_memories": approved_memories,
    }
    commit_updates = await commit_round_memories(commit_state)

    await write_audit_event(
        thread_id=state["thread_id"],
        round_number=next_round,
        node="actioner",
        event_type="route_decision",
        payload={
            "suggested_step": suggestion,
            "approved": True,
            "loop_score": score,
            "skill_preview_ready": skill_preview_ready,
            "score_rationale": score_result.rationale,
            "pending_memory_count": len(pending),
            "approved_memory_count": len(approved_memories),
            "action_review_interrupted": action_review_interrupted,
            "soft_skip": False,
        },
    )

    return {
        "role": "actioner",
        "rounds": next_round,
        "refine_from": suggestion,
        "loop_score": score,
        "skill_preview_ready": skill_preview_ready,
        **commit_updates,
    }
