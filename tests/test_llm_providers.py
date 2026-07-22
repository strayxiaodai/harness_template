"""Unit tests for llm.providers.get_llm."""

from __future__ import annotations

from typing import Any

import llm.providers as providers


def test_get_llm_vllm_uses_openai_compatible_client(
    monkeypatch: Any,
) -> None:
    """vllm provider should construct ChatOpenAI against VLLM_* env."""
    captured: dict[str, Any] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setenv("LLM_PROVIDER", "vllm")
    monkeypatch.setenv("VLLM_BASE_URL", "http://192.168.1.102:8000/v1")
    monkeypatch.setenv(
        "VLLM_MODEL",
        "RedHatAI/Qwen3.6-35B-A3B-NVFP4",
    )
    monkeypatch.setenv("VLLM_API_KEY", "test-key")
    monkeypatch.setattr(
        "langchain_openai.ChatOpenAI",
        FakeChatOpenAI,
    )

    result = providers.get_llm()

    assert isinstance(result, FakeChatOpenAI)
    assert captured["model"] == "RedHatAI/Qwen3.6-35B-A3B-NVFP4"
    assert captured["base_url"] == "http://192.168.1.102:8000/v1"
    assert captured["api_key"] == "test-key"


def test_get_llm_vllm_defaults_api_key_to_empty(
    monkeypatch: Any,
) -> None:
    """When VLLM_API_KEY is unset, api_key should be EMPTY."""
    captured: dict[str, Any] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setenv("LLM_PROVIDER", "vllm")
    monkeypatch.setenv("VLLM_BASE_URL", "http://127.0.0.1:8000/v1")
    monkeypatch.setenv("VLLM_MODEL", "some-model")
    monkeypatch.delenv("VLLM_API_KEY", raising=False)
    monkeypatch.setattr(
        "langchain_openai.ChatOpenAI",
        FakeChatOpenAI,
    )

    providers.get_llm()

    assert captured["api_key"] == "EMPTY"
