# app/audit/logger.py
"""Durable audit logging to Postgres.

When no pool is configured, ``write_audit_event`` logs at debug level and
returns without raising so agents and tests can run without a database.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_audit_pool: Any | None = None


def set_audit_pool(pool: object | None) -> None:
    """Install a pooled connection used by all audit writes.

    The pool is owned by the FastAPI lifespan so this module never opens
    per-call connections on its own.
    """
    global _audit_pool
    _audit_pool = pool


async def write_audit_event(
    *,
    thread_id: str,
    round_number: int,
    node: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Write one audit row when a pool is configured.

    Args:
        thread_id: LangGraph thread id.
        round_number: Current round (1-based after actioner).
        node: Graph node that emitted the event.
        event_type: Event category (e.g. tool_call, route_decision).
        payload: JSON-serializable event body.
    """
    if _audit_pool is None:
        logger.debug(
            "audit pool not configured; skipping event %s for %s",
            event_type,
            thread_id,
        )
        return

    sql = """
        INSERT INTO agent_audit_log (
            thread_id, round_number, node, event_type, payload
        )
        VALUES (%s, %s, %s, %s, %s::jsonb)
    """
    try:
        async with _audit_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    sql,
                    (
                        thread_id,
                        round_number,
                        node,
                        event_type,
                        json.dumps(payload, default=str),
                    ),
                )
    except Exception as exc:
        logger.error("audit write failed for %s: %s", event_type, exc)
