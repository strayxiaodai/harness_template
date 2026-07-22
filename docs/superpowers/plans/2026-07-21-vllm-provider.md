# vLLM Chat Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `LLM_PROVIDER=vllm` so `get_llm()` talks to an OpenAI-compatible vLLM server, switch local `.env` to the LAN endpoint, and document the provider.

**Architecture:** Dedicated `vllm` branch in `llm/providers.py` that constructs `langchain_openai.ChatOpenAI` with `base_url`, `model`, and `api_key` from `VLLM_*` env vars. No new dependencies. RAG embeddings unchanged.

**Tech Stack:** Python, `langchain_openai.ChatOpenAI`, `python-dotenv`, pytest.

**Spec:** [`docs/superpowers/specs/2026-07-21-vllm-provider-design.md`](../specs/2026-07-21-vllm-provider-design.md)

## Global Constraints

- Chat LLM only — do not change RAG embedding providers or `config/settings.yaml`.
- No new Python packages.
- No live/network tests against the LAN vLLM host.
- Do not commit secrets; `.env` is local-only (gitignored).
- Keep existing `openai` / `anthropic` / `ollama` branches unchanged.

---

## Feature → test matrix

| ID | Feature | Automated test | Task |
|----|---------|----------------|------|
| F1 | `LLM_PROVIDER=vllm` builds ChatOpenAI with env kwargs | `test_get_llm_vllm_uses_openai_compatible_client` | 1 |
| F2 | Missing `VLLM_API_KEY` defaults to `EMPTY` | `test_get_llm_vllm_defaults_api_key_to_empty` | 1 |
| F3 | Docs list `vllm` under LLM config | Manual doc check in Task 2 | 2 |

---

## File map

| File | Responsibility |
|------|----------------|
| `llm/providers.py` | Add `vllm` branch in `get_llm()` |
| `tests/test_llm_providers.py` | Unit tests F1–F2 (mock ChatOpenAI) |
| `.env` | Switch active provider to vLLM (local, not committed) |
| `docs/IMPLEMENTATION.md` | Document `vllm` in LLM configuration |
| `docs/histories/2026-07/…` | History entry when code lands |

---

### Task 1: `get_llm()` vllm branch + unit tests (F1–F2)

**Files:**
- Create: `tests/test_llm_providers.py`
- Modify: `llm/providers.py`

**Interfaces:**
- Consumes: existing `get_llm() -> Any` in `llm/providers.py`
- Produces: `get_llm()` accepts `LLM_PROVIDER=vllm` and returns `ChatOpenAI(...)` with:
  - `model` from `VLLM_MODEL` (default `RedHatAI/Qwen3.6-35B-A3B-NVFP4`)
  - `base_url` from `VLLM_BASE_URL` (default `http://127.0.0.1:8000/v1`)
  - `api_key` from `VLLM_API_KEY` (default `EMPTY`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_llm_providers.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm_providers.py -v`

Expected: FAIL with `Unsupported LLM_PROVIDER: vllm` (or similar ValueError from the final raise).

- [ ] **Step 3: Implement the vllm branch**

In `llm/providers.py`, insert this block **before** the final `raise ValueError(...)`, after the `ollama` branch:

```python
    if provider == "vllm":
        from langchain_openai import ChatOpenAI

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
        )
```

Leave `openai`, `anthropic`, and `ollama` branches untouched.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_llm_providers.py -v`

Expected: both tests PASS.

Note: if monkeypatching `"langchain_openai.ChatOpenAI"` fails because the import is local inside `get_llm()`, patch via:

```python
monkeypatch.setattr(
    providers,
    "ChatOpenAI",
    FakeChatOpenAI,
    raising=False,
)
```

That will **not** work for a local import. Prefer:

```python
import langchain_openai

monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeChatOpenAI)
```

and ensure `from langchain_openai import ChatOpenAI` inside `get_llm()` still resolves to the patched class (it does after the module is loaded). If the test still uses the real class, switch the implementation to import the module and use `langchain_openai.ChatOpenAI(...)` so patching is reliable — only if needed to make F1/F2 pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_llm_providers.py llm/providers.py
git commit -m "$(cat <<'EOF'
feat: add vLLM OpenAI-compatible chat provider

EOF
)"
```

---

### Task 2: Local `.env`, docs, history (F3)

**Files:**
- Modify: `.env` (local only — do not `git add`)
- Modify: `docs/IMPLEMENTATION.md` (LLM configuration section ~lines 969–978)
- Create: `docs/histories/2026-07/20260721-HHMM-vllm-provider.md` (use current local time for `HHMM`)

**Interfaces:**
- Consumes: Task 1 `vllm` provider behavior
- Produces: documented env contract matching Task 1 defaults

- [ ] **Step 1: Update local `.env`**

Replace the active LLM block so it looks like:

```bash
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://192.168.1.102:8000/v1
VLLM_MODEL=RedHatAI/Qwen3.6-35B-A3B-NVFP4
VLLM_API_KEY=EMPTY

OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini

ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-sonnet-4-5

# Ollama (inactive)
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://192.168.1.107:11434
# OLLAMA_MODEL=qwen3.6:27b
# OLLAMA_API_KEY=local
```

Preserve existing non-LLM vars (`DATABASE_URL`, `REDIS_URL`, `EXECUTOR_TOOLS` comments, etc.). Do **not** stage `.env`.

- [ ] **Step 2: Update `docs/IMPLEMENTATION.md` LLM section**

Replace the LLM configuration bash block with:

```bash
export LLM_PROVIDER=openai          # openai | anthropic | ollama | vllm
export OPENAI_API_KEY=sk-...
# Ollama local:
export LLM_PROVIDER=ollama
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=qwen3.6:27b
# vLLM OpenAI-compatible:
export LLM_PROVIDER=vllm
export VLLM_BASE_URL=http://127.0.0.1:8000/v1
export VLLM_MODEL=RedHatAI/Qwen3.6-35B-A3B-NVFP4
export VLLM_API_KEY=EMPTY           # optional; defaults to EMPTY
```

- [ ] **Step 3: Write history entry**

Create `docs/histories/2026-07/20260721-HHMM-vllm-provider.md` (fill `HHMM` from `date +%H%M`):

```markdown
## [2026-07-21 HH:MM] | Task: Add vLLM chat provider

### User Query
> Add vLLM support (chat LLM via `.env` / `get_llm()`)

### Changes Overview
- Area: LLM providers
- Key actions: `LLM_PROVIDER=vllm` via ChatOpenAI base_url; local `.env` switched to LAN vLLM; docs + unit tests

### Design Intent
- Dedicated provider name keeps cloud OpenAI keys separate from OpenAI-compatible local servers

### Key Files
- `llm/providers.py`
- `tests/test_llm_providers.py`
- `docs/IMPLEMENTATION.md`
- `.env` (local only)

### Notes
- Embeddings / RAG unchanged
```

- [ ] **Step 4: Verify tests still pass + graphify**

Run:

```bash
pytest tests/test_llm_providers.py -v
graphify update .
```

Expected: both provider tests PASS; graphify completes without error.

- [ ] **Step 5: Commit docs/history only**

```bash
git add docs/IMPLEMENTATION.md docs/histories/2026-07/20260721-*-vllm-provider.md
git commit -m "$(cat <<'EOF'
docs: document vLLM provider and record history

EOF
)"
```

Confirm `git status` does **not** show `.env` staged.

---

## Self-review

1. **Spec coverage:** Goals 1–4 → Task 1 (code/tests) + Task 2 (`.env`/docs). Non-goals respected (no embeddings, no new deps, no live tests).
2. **Placeholders:** None — env values, test code, and doc snippets are concrete.
3. **Type consistency:** `get_llm() -> Any`; env names `VLLM_BASE_URL` / `VLLM_MODEL` / `VLLM_API_KEY` match across tasks and the spec.
