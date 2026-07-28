# app/llm/providers.py
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()


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

        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "qwen3.6:27b"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            temperature=0.2,
        )

    if provider == "vllm":
        from langchain_openai import ChatOpenAI

        # Qwen3 thinking can fill the context window and break
        # with_structured_output (LengthFinishReasonError). Cap tokens and
        # disable thinking by default for harness JSON schemas.
        enable_thinking = os.getenv(
            "VLLM_ENABLE_THINKING",
            "false",
        ).lower() in ("1", "true", "yes")

        return ChatOpenAI(
            model=os.getenv(
                "VLLM_MODEL",
                "RedHatAI/Qwen3.6-35B-A3B-NVFP4",
            ),
            base_url=os.getenv(
                "VLLM_BASE_URL",
                "http://127.0.0.1:8000/v1",
            ),
            api_key=os.getenv("VLLM_API_KEY", "EMPTY"),
            max_tokens=int(os.getenv("VLLM_MAX_TOKENS", "4096")),
            extra_body={
                "chat_template_kwargs": {
                    "enable_thinking": enable_thinking,
                },
            },
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
