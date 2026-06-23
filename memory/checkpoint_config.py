"""Checkpoint backend selection for local dev and production."""

from __future__ import annotations

import os
from pathlib import Path

CheckpointBackend = str

_VALID_BACKENDS = frozenset({"memory", "sqlite", "postgres"})


def resolve_checkpoint_backend() -> CheckpointBackend:
    """Return the configured LangGraph checkpoint backend.

    Priority:
    1. ``CHECKPOINT_BACKEND`` when set to memory, sqlite, or postgres.
    2. ``sqlite`` as the default for local development.

    ``DATABASE_URL`` does not select the checkpoint backend. Use
    ``CHECKPOINT_BACKEND=postgres`` with a Postgres ``DATABASE_URL`` for
    Docker or production.
    """
    explicit = os.getenv("CHECKPOINT_BACKEND", "").strip().lower()
    if explicit in _VALID_BACKENDS:
        return explicit

    return "sqlite"


def sqlite_checkpoint_path() -> str:
    """Return the filesystem path or URI for the SQLite checkpointer."""
    configured = os.getenv("CHECKPOINT_SQLITE_PATH", "").strip()
    if configured:
        return configured

    default = Path("data/checkpoints/langgraph.db")
    default.parent.mkdir(parents=True, exist_ok=True)
    return str(default)
