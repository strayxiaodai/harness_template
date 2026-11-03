# app/llm/providers.py
"""PydanticAI LLM model factory and compatibility adapters."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider
try:
    from pydantic_ai.providers.vllm import VLLMProvider
except ImportError:
    from pydantic_ai.providers.openai import OpenAIProvider as VLLMProvider
from pydantic_ai.settings import ModelSettings

load_dotenv()


class StructuredOutputRunner:
    """Invokes a PydanticAI Agent with structured output for a given schema."""

    def __init__(self, model: Model, schema: type[Any]) -> None:
        self.model = model
        self.schema = schema

    async def ainvoke(self, messages: list[Any]) -> Any:
        system_prompts: list[str] = []
        user_prompts: list[str] = []
        for m in messages:
            content = getattr(m, "content", str(m))
            if hasattr(m, "type") and getattr(m, "type") == "system":
                system_prompts.append(content)
            elif m.__class__.__name__ == "SystemMessage":
                system_prompts.append(content)
            else:
                user_prompts.append(content)

        sys_prompt = "\n\n".join(system_prompts).strip() if system_prompts else None
        agent = Agent(
            model=self.model,
            output_type=self.schema,
            system_prompt=sys_prompt,
        )
        prompt = "\n\n".join(user_prompts).strip() if user_prompts else "Generate structured output"
        res = await agent.run(prompt)
        return res.output


class BoundToolsRunner:
    """Adapter invoking a PydanticAI model/agent with tools."""

    def __init__(self, model: Model, tools: list[Any]) -> None:
        self.model = model
        self.tools = tools

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        # If model is TestModel or custom mock, handle request directly
        if isinstance(self.model, TestModel):
            # Format minimal request for TestModel
            from pydantic_ai.messages import ModelRequest, UserPromptPart
            from pydantic_ai.models import ModelRequestParameters

            prompt = "\n\n".join(getattr(m, "content", str(m)) for m in messages)
            req = ModelRequest(parts=[UserPromptPart(content=prompt)])
            resp: ModelResponse = await self.model.request([req], None, ModelRequestParameters())
            tool_calls = []
            content_parts = []
            for p in resp.parts:
                if isinstance(p, ToolCallPart):
                    tool_calls.append(
                        {
                            "name": p.tool_name,
                            "args": p.args,
                            "id": p.tool_call_id,
                            "type": "tool_call",
                        }
                    )
                elif isinstance(p, TextPart):
                    content_parts.append(p.content)
            return AIMessage(content="".join(content_parts), tool_calls=tool_calls)

        # For live models, run Agent with tools
        agent = Agent(self.model, tools=self.tools)
        prompt = "\n\n".join(getattr(m, "content", str(m)) for m in messages)
        res = await agent.run(prompt)
        return AIMessage(content=str(res.output))


class PydanticAIModelAdapter(Model):
    """Wraps a PydanticAI Model with convenience helpers for LangGraph harnesses."""

    def __init__(self, model: Model) -> None:
        self._model = model

    @property
    def model(self) -> Model:
        return self._model

    @property
    def model_name(self) -> str:
        return getattr(self._model, "model_name", "model")

    @property
    def system(self) -> str | None:
        return getattr(self._model, "system", None)

    @property
    def base_url(self) -> str | None:
        provider = getattr(self._model, "provider", None)
        raw = getattr(provider, "base_url", None)
        return str(raw).rstrip("/") if raw else None

    @property
    def api_key(self) -> str | None:
        provider = getattr(self._model, "provider", None)
        client = getattr(provider, "client", None)
        return getattr(client, "api_key", getattr(provider, "api_key", None))

    @property
    def max_tokens(self) -> int | None:
        settings = getattr(self._model, "settings", None)
        if isinstance(settings, dict):
            return settings.get("max_tokens")
        return getattr(settings, "max_tokens", None)

    @property
    def extra_body(self) -> dict[str, Any] | None:
        settings = getattr(self._model, "settings", None)
        if isinstance(settings, dict):
            return settings.get("extra_body")
        return getattr(settings, "extra_body", None)


    def with_structured_output(self, schema: type[Any]) -> StructuredOutputRunner:
        """Return a structured output runner producing instances of schema."""
        return StructuredOutputRunner(self._model, schema)

    def bind_tools(self, tools: list[Any]) -> BoundToolsRunner:
        """Return a runner with tools bound."""
        return BoundToolsRunner(self._model, tools)

    def create_agent(
        self,
        output_type: type[Any] | None = None,
        system_prompt: str | None = None,
        tools: list[Any] | None = None,
        toolsets: list[Any] | None = None,
        retries: int | None = None,
    ) -> Agent:
        """Create a PydanticAI Agent backed by this model."""
        return Agent(
            model=self._model,
            output_type=output_type,
            system_prompt=system_prompt,
            tools=tools or [],
            toolsets=toolsets or [],
            retries=retries or 1,
        )

    async def request(self, *args: Any, **kwargs: Any) -> Any:
        return await self._model.request(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._model, name)


def get_model(provider_name: str | None = None) -> Model:
    """Return a raw PydanticAI Model instance based on LLM_PROVIDER."""
    provider = (provider_name or os.getenv("LLM_PROVIDER", "openai")).lower()

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        provider_obj = OpenAIProvider(api_key=api_key) if api_key else OpenAIProvider(api_key="EMPTY")
        return OpenAIChatModel(os.getenv("OPENAI_MODEL", "gpt-4o-mini"), provider=provider_obj)

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY") or "EMPTY"
        return AnthropicModel(
            os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
            provider=AnthropicProvider(api_key=api_key),
        )

    if provider == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip()
        if not base_url.rstrip("/").endswith("/v1"):
            base_url = f"{base_url.rstrip('/')}/v1"
        return OllamaModel(
            os.getenv("OLLAMA_MODEL", "qwen3.8:27b"),
            provider=OllamaProvider(base_url=base_url),
        )

    if provider == "vllm":
        enable_thinking = os.getenv(
            "VLLM_ENABLE_THINKING",
            "false",
        ).lower() in ("1", "true", "yes")

        base_url = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8000/v1")
        api_key = os.getenv("VLLM_API_KEY", "EMPTY")
        max_tokens = int(os.getenv("VLLM_MAX_TOKENS", "4096"))
        model_name = os.getenv(
            "VLLM_MODEL",
            "RedHatAI/Qwen3.6-35B-A3B-NVFP4",
        )

        settings = ModelSettings(
            max_tokens=max_tokens,
            extra_body={
                "chat_template_kwargs": {
                    "enable_thinking": enable_thinking,
                },
            },
        )
        return OpenAIChatModel(
            model_name,
            provider=VLLMProvider(base_url=base_url, api_key=api_key),
            settings=settings,
        )

    if provider == "test":
        return TestModel()

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def get_llm(provider_name: str | None = None) -> PydanticAIModelAdapter:
    """Return a PydanticAI model adapter based on LLM_PROVIDER."""
    return PydanticAIModelAdapter(get_model(provider_name))
