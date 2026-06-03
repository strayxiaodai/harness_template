# app/llm/providers.py
import os
from typing import Any


def get_llm() -> Any:
    """Return a chat model based on LLM_PROVIDER."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=os.getenv("OLLAMA_MODEL", "qwen3.6:27b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://192.168.1.107:11434"),
        temperature=0.2,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")