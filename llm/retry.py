# app/llm/retry.py
"""Bounded retry wrapper for LLM calls and PydanticAI agent invocations."""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

TRANSIENT_ERRORS: tuple[type[Exception], ...] = (
    TimeoutError,
    ConnectionError,
    ModelAPIError,
    ModelHTTPError,
)


@retry(
    retry=retry_if_exception_type(TRANSIENT_ERRORS),
    wait=wait_exponential_jitter(initial=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def call_llm(runnable: Any, messages: list[Any]) -> Any:
    """Invoke an LLM runnable or PydanticAI Agent with bounded retry/backoff."""
    if isinstance(runnable, Agent):
        user_prompts = [
            getattr(m, "content", str(m))
            for m in messages
            if not (hasattr(m, "type") and getattr(m, "type") == "system")
            and m.__class__.__name__ != "SystemMessage"
        ]
        prompt = "\n\n".join(user_prompts).strip() if user_prompts else "Process"
        res = await runnable.run(prompt)
        return res.output

    if hasattr(runnable, "ainvoke"):
        return await runnable.ainvoke(messages)

    if callable(runnable):
        return await runnable(messages)

    raise TypeError(f"Unsupported runnable type: {type(runnable)}")


@retry(
    retry=retry_if_exception_type(TRANSIENT_ERRORS),
    wait=wait_exponential_jitter(initial=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def run_agent(agent: Agent, prompt: str, **kwargs: Any) -> Any:
    """Invoke a PydanticAI agent with bounded retry/backoff and return its output."""
    res = await agent.run(prompt, **kwargs)
    return getattr(res, "output", res)
