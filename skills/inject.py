"""Inject distilled skills into harness agent prompts."""

from __future__ import annotations

from graph.state import AgentState


def skill_prompt_prefix(state: AgentState) -> str:
    """Return a markdown block for skill context, or empty when unset."""
    body = str(state.get("skill_context", "")).strip()
    if not body:
        return ""
    slug = str(state.get("skill_slug", "skill"))
    return f"## Harness skill `{slug}`\n{body}\n\n"
