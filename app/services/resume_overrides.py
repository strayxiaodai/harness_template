"""Normalize HITL resume overrides before checkpoint updates."""

from __future__ import annotations

from typing import Any


def apply_resume_overrides(
    current: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Merge learning/refine overrides and keep approved in sync.

    Args:
        current: Latest checkpoint values.
        patch: Raw override dict from ``ResumeOverrides.model_dump``.

    Returns:
        Patch suitable for ``graph.aupdate_state``, with learning merged onto
        existing lessons, ``approved`` derived from learning verdict when
        present, and ``refine_from`` mirrored onto ``learning.suggested_step``
        so the actioner does not overwrite the operator choice.
    """
    out = dict(patch)
    existing_learning = dict(current.get("learning") or {})
    merged: dict[str, Any] | None = None

    if "learning" in out and out["learning"] is not None:
        learning_patch = out["learning"]
        if not isinstance(learning_patch, dict):
            learning_patch = dict(learning_patch)
        merged = {**existing_learning, **learning_patch}

    if "refine_from" in out and out["refine_from"] is not None:
        base = merged if merged is not None else existing_learning
        merged = {**base, "suggested_step": out["refine_from"]}

    if merged is not None:
        out["learning"] = merged
        verdict = merged.get("verdict")
        if verdict in ("pass", "fail"):
            out["approved"] = verdict == "pass"

    return out
