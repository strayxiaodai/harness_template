"""Uvicorn entry point for the harness HTTP API."""

from app.core.app import create_app

app = create_app()
