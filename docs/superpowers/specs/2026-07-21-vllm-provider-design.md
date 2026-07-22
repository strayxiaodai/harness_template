# vLLM chat provider support

Date: 2026-07-21  
Status: approved for planning  
Surface: `llm/providers.py`, local `.env`, `docs/IMPLEMENTATION.md`  
Related:

- [`docs/IMPLEMENTATION.md`](../../IMPLEMENTATION.md) (LLM configuration)
- [`llm/providers.py`](../../../llm/providers.py) (`get_llm()`)

## Problem

The harness can talk to OpenAI, Anthropic, and Ollama, but not a local or LAN
vLLM server. Operators who already serve models via vLLM’s OpenAI-compatible
HTTP API must either spoof the OpenAI env vars or stay on Ollama.

## Goals

1. Support `LLM_PROVIDER=vllm` in `get_llm()`.
2. Configure via `VLLM_BASE_URL`, `VLLM_MODEL`, and optional `VLLM_API_KEY`.
3. Switch the local `.env` to vLLM with the operator’s LAN endpoint and model.
4. Document the provider in `docs/IMPLEMENTATION.md`.

## Non-goals

- RAG / embedding provider changes (`settings.yaml` embedding stays as-is).
- New Python dependencies.
- Live integration tests against the LAN vLLM host.
- Changing OpenAI or Ollama provider behavior.

## Decisions

| Decision | Choice |
| --- | --- |
| Client | `langchain_openai.ChatOpenAI` against OpenAI-compatible `/v1` |
| Provider name | `vllm` (dedicated branch, not reuse of `openai`) |
| API key default | `EMPTY` when `VLLM_API_KEY` unset |
| Base URL default (code) | `http://127.0.0.1:8000/v1` |
| Local `.env` active | `LLM_PROVIDER=vllm` with LAN URL + model below |
| Ollama in `.env` | Keep as commented inactive block |
| Embeddings | Unchanged |

## Local `.env` values

```bash
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://192.168.1.102:8000/v1
VLLM_MODEL=RedHatAI/Qwen3.6-35B-A3B-NVFP4
VLLM_API_KEY=EMPTY
```

Ollama vars remain in `.env` but commented out.

## Implementation sketch

In `llm/providers.py`, after the existing provider branches:

```python
if provider == "vllm":
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=os.getenv("VLLM_MODEL", "RedHatAI/Qwen3.6-35B-A3B-NVFP4"),
        base_url=os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8000/v1"),
        api_key=os.getenv("VLLM_API_KEY", "EMPTY"),
    )
```

Unknown providers continue to raise `ValueError`.

## Docs

Update the LLM configuration block in `docs/IMPLEMENTATION.md`:

- List `openai | anthropic | ollama | vllm` for `LLM_PROVIDER`.
- Add a short vLLM example with `VLLM_BASE_URL` / `VLLM_MODEL` / `VLLM_API_KEY`.

## Tests

Add a unit test (no network) that:

1. Sets `LLM_PROVIDER=vllm` plus the three env vars via monkeypatch.
2. Mocks `langchain_openai.ChatOpenAI`.
3. Asserts `get_llm()` constructs it with the expected `model`, `base_url`, and
   `api_key`.

## Success criteria

- `LLM_PROVIDER=vllm` returns a `ChatOpenAI` pointed at the configured base URL.
- Local `.env` selects vLLM with the LAN endpoint and model above.
- `docs/IMPLEMENTATION.md` documents the new provider.
- Unit test passes without contacting the LAN host.
