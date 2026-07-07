"""HTTP API configuration."""

from __future__ import annotations

API_TITLE = "Enterprise LangGraph Harness"

CORS_ALLOW_ORIGINS: list[str] = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]
