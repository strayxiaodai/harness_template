"""FastAPI lifespan: checkpointer, pools, and compiled LangGraph instances."""

from memory.checkpoint import graph_lifespan

__all__ = ["graph_lifespan"]
