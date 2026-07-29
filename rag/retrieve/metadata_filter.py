"""Extract metadata filter hints from user queries."""

from __future__ import annotations

import re
from typing import Any

# Maps common query terms to known module names
_MODULE_KEYWORDS: dict[str, str] = {
    "agent": "agent",
    "graph": "graph",
    "rag": "rag",
    "app": "app",
    "config": "config",
    "test": "tests",
    "frontend": "app",
    "api": "app",
    "ingest": "rag",
    "retrieve": "rag",
    "memory": "rag",
}

_FILE_TYPE_KEYWORDS: dict[str, str] = {
    "python": "py",
    "markdown": "md",
    "yaml": "yaml",
    "yml": "yml",
    "config": "yaml",
    "script": "py",
    "documentation": "md",
    "docs": "md",
}

_WORD_RE = re.compile(r"\b\w+\b")


def extract_metadata_hints(query: str) -> dict[str, Any] | None:
    """Extract structured metadata filter hints from a natural language query.

    Uses keyword matching to infer module and file_type filters.

    Args:
        query: User search query.

    Returns:
        Dict of metadata field to filter value, or None if no hints found.
    """
    words = [w.lower() for w in _WORD_RE.findall(query)]
    hints: dict[str, Any] = {}

    for word in words:
        if word in _MODULE_KEYWORDS and "module" not in hints:
            hints["module"] = _MODULE_KEYWORDS[word]
        if word in _FILE_TYPE_KEYWORDS and "file_type" not in hints:
            hints["file_type"] = _FILE_TYPE_KEYWORDS[word]

    return hints or None
