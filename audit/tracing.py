"""Observability and tracing for agent workflows via Langfuse."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_tracing_initialized: bool = False
_langfuse_client: Any | None = None


def is_langfuse_enabled() -> bool:
    """Return True if Langfuse is configured and enabled in the environment."""
    raw = os.getenv("LANGFUSE_ENABLED", "").strip().lower()
    if raw in ("false", "0", "no"):
        return False
    if raw in ("true", "1", "yes"):
        return True

    # In test environments without explicit enablement, keep tracing disabled
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    return bool(public_key and secret_key)


def init_tracing(
    *,
    enabled: bool | None = None,
    send_to_logfire: str | bool | None = None,
) -> bool:
    """Initialize Langfuse client and tracing.

    Args:
        enabled: Explicitly enable or disable Langfuse. If None, checks environment.
        send_to_logfire: Legacy alias for compatibility with existing callers.

    Returns:
        True if tracing initialization succeeded or was skipped cleanly, False on failure.
    """
    global _tracing_initialized, _langfuse_client
    if _tracing_initialized:
        return True

    if enabled is not None:
        target_enabled = enabled
    elif send_to_logfire is not None:
        if isinstance(send_to_logfire, bool):
            target_enabled = send_to_logfire
        else:
            raw = str(send_to_logfire).strip().lower()
            target_enabled = raw not in ("false", "0", "no")
    else:
        target_enabled = is_langfuse_enabled()

    if not target_enabled:
        _tracing_initialized = True
        logger.debug("Langfuse tracing skipped (not enabled or credentials not present)")
        return True

    try:
        import langfuse

        _langfuse_client = langfuse.get_client()
        _tracing_initialized = True
        logger.info("Langfuse tracing initialized")
        return True
    except Exception as exc:
        logger.debug("Langfuse tracing initialization skipped or failed: %s", exc)
        return False


def get_langfuse_handler(
    thread_id: str | None = None,
    task: str | None = None,
) -> Any | None:
    """Return a Langfuse CallbackHandler bound to the thread session if enabled."""
    if not is_langfuse_enabled():
        return None

    try:
        from langfuse.langchain import CallbackHandler

        return CallbackHandler()
    except Exception as exc:
        logger.debug("Failed to create Langfuse CallbackHandler: %s", exc)
        return None


def trace_event(event_type: str, payload: dict[str, Any]) -> None:
    """Record an audit or workflow event into Langfuse when available."""
    global _langfuse_client
    if not is_langfuse_enabled():
        return
    try:
        import langfuse

        client = _langfuse_client or langfuse.get_client()
        client.create_event(
            name=f"audit_event: {event_type}",
            metadata=payload,
        )
    except Exception as exc:
        logger.debug("Failed to record Langfuse event %s: %s", event_type, exc)


def flush_tracing() -> None:
    """Flush any pending Langfuse events and spans."""
    global _langfuse_client
    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
        except Exception:
            pass
