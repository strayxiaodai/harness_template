"""HITL clarification helper shared by harness agent nodes."""

from __future__ import annotations

import textwrap
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

    answered_ids = {row["question_id"] for row in normalized}
    for item in question_dicts:
        qid = str(item.get("id", ""))
        default_val = item.get("default")
        if qid and default_val and qid not in answered_ids:
            normalized.append(
                {
                    "question_id": qid,
                    "question": prompts_by_id.get(qid, ""),
                    "answer": str(default_val),
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


def format_ascii_pipeline(steps: list[str], max_width: int = 70) -> str:
    """Render a clean vertical execution tree with full readable text (zero truncation)."""
    if not steps:
        return ""
    lines: list[str] = []
    total = len(steps)
    for i, s in enumerate(steps, 1):
        clean = " ".join(s.strip().split())
        if total == 1:
            branch = "●"
            sub_prefix = "  "
        elif i == 1:
            branch = "┌──"
            sub_prefix = "│   "
        elif i == total:
            branch = "└──"
            sub_prefix = "    "
        else:
            branch = "├──"
            sub_prefix = "│   "

        first_prefix = f"{branch} [{i}] "
        available_width = max(30, max_width - len(first_prefix))
        wrapped = textwrap.wrap(clean, width=available_width)
        if not wrapped:
            lines.append(first_prefix)
        else:
            lines.append(first_prefix + wrapped[0])
            for follow_line in wrapped[1:]:
                lines.append(sub_prefix + "    " + follow_line)
    return "\n".join(lines)


def format_planner_clarification(steps: list[str], rationale: str) -> str:
    """Format planner clarification details into a readable vertical tree with sectioned rationale."""
    flow = format_ascii_pipeline(steps)

    formatted_rationale = rationale.strip()
    keywords = [
        "Goal:",
        "Assumptions surfaced:",
        "Format assumption:",
        "Assumptions:",
        "Trade-offs:",
        "Spec-driven vs exploratory:",
        "Risk:",
        "Risks:",
        "Risks & Mitigations:",
        "Verification:",
    ]
    for kw in keywords:
        formatted_rationale = formatted_rationale.replace(f" {kw}", f"\n- **{kw.rstrip(':')}:**")
        if formatted_rationale.startswith(kw):
            formatted_rationale = f"- **{kw.rstrip(':')}:** {formatted_rationale[len(kw):].strip()}"

    parts = []
    if flow:
        parts.append(f"```text\n{flow}\n```")
    if formatted_rationale:
        parts.append(f"### Rationale\n{formatted_rationale}")

    return "\n\n".join(parts)


def format_executor_clarification(
    summary: str,
    changes: list[str] | None = None,
    verification: list[str] | None = None,
    risks: list[str] | None = None,
) -> str:
    """Format executor clarification details into a readable ASCII-diagrammed block."""
    flow = "[Inspect Context] ──> [Apply Changes] ──> [Verify Output] ──> [DONE ✓]"
    parts = [f"```text\n{flow}\n```"]
    if summary:
        parts.append(f"### Summary\n{summary.strip()}")
    if changes:
        changes_list = "\n".join(f"- {c.strip()}" for c in changes if c.strip())
        if changes_list:
            parts.append(f"### Changes\n{changes_list}")
    if verification:
        verify_list = "\n".join(f"- {v.strip()}" for v in verification if v.strip())
        if verify_list:
            parts.append(f"### Verification\n{verify_list}")
    if risks:
        risks_list = "\n".join(f"- {r.strip()}" for r in risks if r.strip())
        if risks_list:
            parts.append(f"### Risks & Watchpoints\n{risks_list}")
    return "\n\n".join(parts)


def format_learner_clarification(
    verdict: str,
    reason: str,
    suggested_step: str,
    lessons: Any = None,
) -> str:
    """Format learner evaluation clarification details with decision flow."""
    is_pass = str(verdict).lower() == "pass"
    if is_pass:
        flow = "[Execution Done] ──> [Evaluation: PASS ✓] ──> [Actioner: Finish & Store]"
    else:
        flow = "[Execution Done] ──> [Evaluation: FAIL ✗] ──> [Planner: Re-plan & Fix]"

    parts = [f"```text\n{flow}\n```"]
    if reason:
        parts.append(f"### Evaluation Reason\n{reason.strip()}")

    if lessons is not None:
        worked = (
            getattr(lessons, "worked", None)
            or (lessons.get("worked") if isinstance(lessons, dict) else [])
        )
        failed = (
            getattr(lessons, "failed", None)
            or (lessons.get("failed") if isinstance(lessons, dict) else [])
        )
        risks = (
            getattr(lessons, "risks", None)
            or (lessons.get("risks") if isinstance(lessons, dict) else [])
        )
        next_time = (
            getattr(lessons, "next_time", None)
            or (lessons.get("next_time") if isinstance(lessons, dict) else [])
        )

        lesson_items = []
        if worked:
            lesson_items.append("- **What worked:** " + "; ".join(str(w) for w in worked))
        if failed:
            lesson_items.append("- **What failed:** " + "; ".join(str(f) for f in failed))
        if risks:
            lesson_items.append("- **Risks noted:** " + "; ".join(str(r) for r in risks))
        if next_time:
            lesson_items.append("- **Next time:** " + "; ".join(str(n) for n in next_time))

        if lesson_items:
            parts.append("### Lessons Learned\n" + "\n".join(lesson_items))

    parts.append(f"**Suggested Next Step:** `{suggested_step}`")
    return "\n\n".join(parts)


def format_ascii_score_bar(score: int, total: int = 100, width: int = 10) -> str:
    """Render a simple ASCII progress bar for loop quality score."""
    clamped = max(0, min(total, int(score)))
    filled = int(round((clamped / total) * width))
    empty = width - filled
    return "[" + "█" * filled + "░" * empty + "]"

