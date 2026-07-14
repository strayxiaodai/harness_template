"""HITL clarification helper shared by harness agent nodes."""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from graph.schemas import ClarificationAnswer, ClarificationQuestion
from graph.state import AgentState


def format_clarification_block(state: AgentState | dict[str, object]) -> str:
    """Format prior human clarification answers for agent prompts."""
    answers = state.get("clarification_answers") or []
    if not answers:
        return ""
    lines = ["Prior human clarifications:"]
    for item in answers:
        if not isinstance(item, dict):
            continue
        qid = str(item.get("question_id", ""))
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if question:
            lines.append(f"- [{qid}] {question} → {answer}")
        else:
            lines.append(f"- [{qid}] {answer}")
    return "\n".join(lines) + "\n\n"


def _as_question_dicts(
    questions: list[ClarificationQuestion] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize question models or dicts to plain dicts."""
    out: list[dict[str, Any]] = []
    for question in questions:
        if isinstance(question, ClarificationQuestion):
            out.append(question.model_dump())
        else:
            out.append(dict(question))
    return out


def normalize_clarification_answers(
    resumed: Any,
    questions: list[ClarificationQuestion] | list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Normalize a Command(resume=...) payload into answer dicts.

    Args:
        resumed: Value returned from ``interrupt()`` after HITL resume.
        questions: Questions that were surfaced in the interrupt payload.

    Returns:
        List of ``{question_id, question, answer}`` dicts for state/prompts.
    """
    question_dicts = _as_question_dicts(questions)
    prompts_by_id = {
        str(item.get("id", "")): str(item.get("prompt", ""))
        for item in question_dicts
    }

    raw_answers: list[Any]
    if resumed is None or resumed is True:
        raw_answers = []
    elif isinstance(resumed, dict) and "answers" in resumed:
        raw_answers = list(resumed.get("answers") or [])
    elif isinstance(resumed, list):
        raw_answers = resumed
    else:
        raw_answers = [{"question_id": "general", "answer": str(resumed)}]

    normalized: list[dict[str, str]] = []
    for item in raw_answers:
        if isinstance(item, ClarificationAnswer):
            qid = item.question_id
            answer = item.answer
        elif isinstance(item, dict):
            qid = str(item.get("question_id", "")).strip()
            answer = str(item.get("answer", "")).strip()
        else:
            continue
        if not qid or not answer:
            continue
        normalized.append(
            {
                "question_id": qid,
                "question": prompts_by_id.get(qid, ""),
                "answer": answer,
            }
        )
    return normalized


def ask_clarification(
    state: AgentState,
    questions: list[ClarificationQuestion] | list[dict[str, Any]],
    *,
    reason: str = "",
    node: str = "",
) -> list[dict[str, str]]:
    """Pause for structured clarification when HITL is enabled.

    When ``human_in_the_loop`` is false, returns an empty list so the caller
    proceeds best-effort without blocking. When HITL is on, surfaces a
    ``kind: clarification`` interrupt (same pause/resume path as skill
    preview) and returns the operator's structured answers.

    Args:
        state: Current harness state.
        questions: Questions to ask the operator.
        reason: Short explanation of why clarification is needed.
        node: Node name for the interrupt payload.

    Returns:
        Normalized clarification answer dicts (empty when HITL is off).
    """
    question_dicts = _as_question_dicts(questions)
    if not question_dicts:
        return []
    if not state.get("human_in_the_loop"):
        return []

    resumed = interrupt(
        {
            "kind": "clarification",
            "node": node or str(state.get("role") or ""),
            "reason": reason,
            "questions": question_dicts,
        }
    )
    return normalize_clarification_answers(resumed, question_dicts)


def merge_clarification_answers(
    prior: list[dict[str, str]] | None,
    new: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Merge new answers over prior ones by ``question_id``."""
    merged: dict[str, dict[str, str]] = {}
    for item in prior or []:
        qid = str(item.get("question_id", "")).strip()
        if qid:
            merged[qid] = {
                "question_id": qid,
                "question": str(item.get("question", "")),
                "answer": str(item.get("answer", "")),
            }
    for item in new:
        qid = str(item.get("question_id", "")).strip()
        if qid:
            merged[qid] = item
    return list(merged.values())
