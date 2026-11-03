"""Unit tests for Langfuse tracing integration."""

import pytest

from audit.logger import write_audit_event
from audit.tracing import (
    flush_tracing,
    get_langfuse_handler,
    init_tracing,
    is_langfuse_enabled,
    trace_event,
)


def test_init_tracing_local() -> None:
    """init_tracing configures tracing cleanly without raising."""
    result = init_tracing(enabled=False)
    assert result is True


def test_is_langfuse_enabled_default_in_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """In test environment without explicit enablement, langfuse is disabled."""
    monkeypatch.delenv("LANGFUSE_ENABLED", raising=False)
    assert is_langfuse_enabled() is False
    assert get_langfuse_handler(thread_id="t1") is None


def test_get_langfuse_handler_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """When enabled, get_langfuse_handler returns a CallbackHandler instance."""
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-mock")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-mock")

    handler = get_langfuse_handler(thread_id="t1", task="Test task")
    assert handler is not None


def test_trace_event_does_not_raise() -> None:
    """trace_event handles arbitrary payloads cleanly."""
    trace_event("test_event", {"thread_id": "t1", "action": "test"})
    flush_tracing()


@pytest.mark.asyncio
async def test_write_audit_event_integrates_with_tracing() -> None:
    """write_audit_event emits trace events safely when pool is None."""
    await write_audit_event(
        thread_id="t-trace-1",
        round_number=1,
        node="executor",
        event_type="tool_call",
        payload={"tool": "read_file", "status": "ok"},
    )
