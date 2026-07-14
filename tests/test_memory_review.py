"""Tests for action-review resume mapping helpers."""

from __future__ import annotations

from agent.memory_review import (
    clear_pending,
    load_pending,
    map_resume_to_approved,
    stash_pending,
)


def test_bare_resume_keeps_all_pending() -> None:
    pending = [
        {
            "id": "m0",
            "content": "prefers pytest",
            "memory_type": "preference",
            "importance": 0.8,
        },
    ]
    assert map_resume_to_approved(pending, True) == [
        {
            "content": "prefers pytest",
            "memory_type": "preference",
            "importance": 0.8,
        },
    ]


def test_empty_memories_stores_nothing() -> None:
    pending = [
        {
            "id": "m0",
            "content": "x",
            "memory_type": "fact",
            "importance": 0.5,
        },
    ]
    assert map_resume_to_approved(pending, {"memories": []}) == []


def test_keep_edit_and_drop() -> None:
    pending = [
        {
            "id": "m0",
            "content": "old",
            "memory_type": "fact",
            "importance": 0.5,
        },
        {
            "id": "m1",
            "content": "drop me",
            "memory_type": "fact",
            "importance": 0.5,
        },
    ]
    resume = {
        "memories": [
            {
                "id": "m0",
                "keep": True,
                "content": "new",
                "memory_type": "preference",
                "importance": 0.9,
            },
            {"id": "m1", "keep": False},
        ],
    }
    assert map_resume_to_approved(pending, resume) == [
        {
            "content": "new",
            "memory_type": "preference",
            "importance": 0.9,
        },
    ]


def test_omitted_id_when_list_provided_is_drop() -> None:
    pending = [
        {
            "id": "m0",
            "content": "a",
            "memory_type": "fact",
            "importance": 0.5,
        },
        {
            "id": "m1",
            "content": "b",
            "memory_type": "fact",
            "importance": 0.5,
        },
    ]
    resume = {"memories": [{"id": "m0", "keep": True, "content": "a"}]}
    assert map_resume_to_approved(pending, resume) == [
        {"content": "a", "memory_type": "fact", "importance": 0.5},
    ]


def test_pending_cache_round_trips_empty_lists() -> None:
    """Empty pending lists are real cache hits for skill-only interrupts."""
    thread_id = "cache-empty"
    cursor = 12

    clear_pending(thread_id, cursor)
    stash_pending(thread_id, cursor, [])

    assert load_pending(thread_id, cursor) == []

    clear_pending(thread_id, cursor)
    assert load_pending(thread_id, cursor) is None


def test_pending_cache_round_trips_score() -> None:
    """Action-review re-entry can reuse the stashed loop score."""
    from agent.memory_review import load_score

    thread_id = "cache-score"
    cursor = 14
    clear_pending(thread_id, cursor)
    stash_pending(
        thread_id,
        cursor,
        [{"id": "m0", "content": "x", "memory_type": "fact", "importance": 0.5}],
        score=82,
        score_rationale="stable",
    )
    assert load_score(thread_id, cursor) == (82, "stable")
    clear_pending(thread_id, cursor)
    assert load_score(thread_id, cursor) is None


def test_pending_cache_returns_copies() -> None:
    """Callers should not mutate pending cache contents by accident."""
    thread_id = "cache-copy"
    cursor = 13
    pending = [
        {
            "id": "m0",
            "content": "prefers pytest",
            "memory_type": "preference",
            "importance": 0.8,
        },
    ]

    clear_pending(thread_id, cursor)
    stash_pending(thread_id, cursor, pending)
    pending[0]["content"] = "changed after stash"
    loaded = load_pending(thread_id, cursor)

    assert loaded == [
        {
            "id": "m0",
            "content": "prefers pytest",
            "memory_type": "preference",
            "importance": 0.8,
        },
    ]

    assert loaded is not None
    loaded[0]["content"] = "changed after load"
    assert load_pending(thread_id, cursor) == [
        {
            "id": "m0",
            "content": "prefers pytest",
            "memory_type": "preference",
            "importance": 0.8,
        },
    ]

    clear_pending(thread_id, cursor)
