"""Base tool decorator and wrappers supporting PydanticAI and LangChain interfaces."""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

from pydantic import BaseModel


class HarnessTool:
    """Callable tool wrapper compatible with both PydanticAI Agent and LangChain tool APIs."""

    def __init__(
        self,
        func: Callable[..., Any],
        name: str | None = None,
        description: str | None = None,
        args_schema: type[BaseModel] | None = None,
    ) -> None:
        self._func = func
        self.name = name or getattr(func, "__name__", "tool")
        self.description = description or func.__doc__ or ""
        self.args_schema = args_schema
        self.__name__ = self.name
        self.__doc__ = self.description
        functools.update_wrapper(self, func)

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if inspect.iscoroutinefunction(self._func):
            return await self._func(*args, **kwargs)
        return self._func(*args, **kwargs)

    async def ainvoke(self, args: Any) -> Any:
        if isinstance(args, BaseModel):
            args = args.model_dump()
        if isinstance(args, dict):
            return await self(**args)
        return await self(args)

    def invoke(self, args: Any) -> Any:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # In an existing loop, create task or return coroutine
            return self.ainvoke(args)
        return asyncio.run(self.ainvoke(args))


def harness_tool(
    name: str | None = None,
    description: str | None = None,
    args_schema: type[BaseModel] | None = None,
) -> Any:
    """Decorator converting a function into a HarnessTool."""
    if callable(name):
        func = name
        return HarnessTool(func)

    def decorator(func: Callable[..., Any]) -> HarnessTool:
        return HarnessTool(
            func,
            name=name,
            description=description,
            args_schema=args_schema,
        )

    return decorator


async def execute_tool(tool: Any, args: Any) -> Any:
    """Execute a tool regardless of whether it's a HarnessTool, LangChain tool, or raw callable."""
    if hasattr(tool, "ainvoke"):
        return await tool.ainvoke(args)

    if isinstance(args, BaseModel):
        args = args.model_dump()

    is_coro = inspect.iscoroutinefunction(tool) or (
        callable(tool) and inspect.iscoroutinefunction(getattr(tool, "__call__", None))
    )

    if isinstance(args, dict):
        if is_coro:
            return await tool(**args)
        res = tool(**args)
        if inspect.isawaitable(res):
            return await res
        return res

    if is_coro:
        return await tool(args)
    res = tool(args)
    if inspect.isawaitable(res):
        return await res
    return res

