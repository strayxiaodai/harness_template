"""Tests for audit logger."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from audit.logger import set_audit_pool, write_audit_event


@pytest.mark.asyncio
async def test_write_audit_event_skips_without_pool() -> None:
    """No pool configured should not raise."""
    set_audit_pool(None)
    await write_audit_event(
        thread_id="t1",
        round_number=1,
        node="executor",
        event_type="tool_call",
        payload={"tool": "read_file"},
    )


@pytest.mark.asyncio
async def test_write_audit_event_inserts_row() -> None:
    """Configured pool should execute an INSERT."""
    cursor = AsyncMock()
    conn = MagicMock()
    conn.cursor.return_value.__aenter__ = AsyncMock(return_value=cursor)
    conn.cursor.return_value.__aexit__ = AsyncMock(return_value=False)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)

    set_audit_pool(pool)
    try:
        await write_audit_event(
            thread_id="t1",
            round_number=2,
            node="actioner",
            event_type="route_decision",
            payload={"suggested_step": "executor", "approved": False},
        )
    finally:
        set_audit_pool(None)

    cursor.execute.assert_awaited_once()
    args = cursor.execute.await_args.args
    assert "agent_audit_log" in args[0]
    assert args[1][0] == "t1"
    assert args[1][3] == "route_decision"
