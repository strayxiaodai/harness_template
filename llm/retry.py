# app/llm/retry.py
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

TRANSIENT_ERRORS: tuple[type[Exception], ...] = (
    TimeoutError,
    ConnectionError,
)


@retry(
    retry=retry_if_exception_type(TRANSIENT_ERRORS),
    wait=wait_exponential_jitter(initial=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def call_llm(runnable: Any, messages: list[Any]) -> Any:
    """Invoke an LLM runnable with bounded retry/backoff."""
    return await runnable.ainvoke(messages)
