## [2026-07-21 19:55] | Task: Cap vLLM tokens / disable Qwen thinking

### User Query
> Planner failed with `openai.LengthFinishReasonError` (completion_tokens≈16299 on a ~85-token prompt)

### Changes Overview
- Area: LLM providers (vLLM)
- Key actions: default `max_tokens=4096` and `enable_thinking=false` via env; docs + tests

### Design Intent
- Qwen3 thinking was filling the model context before structured `PlanResult` JSON completed; disable thinking and cap completions for harness schemas

### Files Modified
- `llm/providers.py`
- `tests/test_llm_providers.py`
- `docs/IMPLEMENTATION.md`
- `.env` (local only)
