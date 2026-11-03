"""Unit tests for llm.providers.get_llm and get_model."""

from __future__ import annotations

from typing import Any

from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel

import llm.providers as providers


def test_get_llm_vllm_uses_openai_compatible_client(
    monkeypatch: Any,
) -> None:
    """vllm provider should construct OpenAIChatModel against VLLM_* env."""
    monkeypatch.setenv("LLM_PROVIDER", "vllm")
    monkeypatch.setenv("VLLM_BASE_URL", "http://192.168.1.102:8000/v1")
    monkeypatch.setenv(
        "VLLM_MODEL",
        "RedHatAI/Qwen3.6-35B-A3B-NVFP4",
    )
    monkeypatch.setenv("VLLM_API_KEY", "test-key")

    result = providers.get_llm()

    assert result.model_name == "RedHatAI/Qwen3.6-35B-A3B-NVFP4"
    assert "192.168.1.102:8000" in (result.base_url or "")
    assert result.api_key == "test-key"
    assert result.max_tokens == 4096
    assert result.extra_body == {
        "chat_template_kwargs": {"enable_thinking": False},
    }


def test_get_llm_vllm_defaults_api_key_to_empty(
    monkeypatch: Any,
) -> None:
    """When VLLM_API_KEY is unset, api_key should be EMPTY."""
    monkeypatch.setenv("LLM_PROVIDER", "vllm")
    monkeypatch.setenv("VLLM_BASE_URL", "http://127.0.0.1:8000/v1")
    monkeypatch.setenv("VLLM_MODEL", "some-model")
    monkeypatch.delenv("VLLM_API_KEY", raising=False)

    result = providers.get_llm()

    assert result.api_key == "EMPTY"


def test_get_llm_vllm_respects_max_tokens_and_thinking(
    monkeypatch: Any,
) -> None:
    """VLLM_MAX_TOKENS and VLLM_ENABLE_THINKING should pass through."""
    monkeypatch.setenv("LLM_PROVIDER", "vllm")
    monkeypatch.setenv("VLLM_BASE_URL", "http://127.0.0.1:8000/v1")
    monkeypatch.setenv("VLLM_MODEL", "some-model")
    monkeypatch.setenv("VLLM_MAX_TOKENS", "2048")
    monkeypatch.setenv("VLLM_ENABLE_THINKING", "true")

    result = providers.get_llm()

    assert result.max_tokens == 2048
    assert result.extra_body == {
        "chat_template_kwargs": {"enable_thinking": True},
    }


def test_get_llm_openai_provider(monkeypatch: Any) -> None:
    """openai provider constructs OpenAIChatModel."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    result = providers.get_llm()
    assert isinstance(result.model, OpenAIChatModel)
    assert result.model_name == "gpt-4o-mini"


def test_get_llm_anthropic_provider(monkeypatch: Any) -> None:
    """anthropic provider constructs AnthropicModel."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    result = providers.get_llm()
    assert isinstance(result.model, AnthropicModel)
    assert result.model_name == "claude-sonnet-4-5"


def test_get_llm_ollama_provider(monkeypatch: Any) -> None:
    """ollama provider constructs OllamaModel."""
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3.6:27b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    result = providers.get_llm()
    assert isinstance(result.model, OllamaModel)
    assert result.model_name == "qwen3.6:27b"


def test_get_llm_test_provider(monkeypatch: Any) -> None:
    """test provider constructs TestModel."""
    monkeypatch.setenv("LLM_PROVIDER", "test")

    result = providers.get_llm()
    assert isinstance(result.model, TestModel)
