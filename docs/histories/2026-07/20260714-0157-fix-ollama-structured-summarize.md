## [2026-07-14 01:57] | Task: Fix Ollama structured summarize failure

### User Query
> Debug POST /resume 409 and `Invalid json output` / OUTPUT_PARSING_FAILURE

### Changes Overview
- Area: executor / learner structured summarize after tool loops
- Key actions: stop feeding live tool-call messages into
  `with_structured_output`; pass plain-text tool evidence instead

### Design Intent
Ollama (`qwen3.6:27b`) with default `json_schema` structured output kept
emitting further tool calls (empty content) when prior `ToolMessage` /
tool-call `AIMessage` rows remained in the summarize transcript, so
`PydanticOutputParser` raised `OUTPUT_PARSING_FAILURE`. A fresh summarize
prompt with text evidence fixes parsing without changing the tool loop.
The 409 on `/resume` is separate: resume requires
`human_in_the_loop` on the checkpoint; Continue-from-error still hits
`/resume` even when that flag is missing or the snapshot is empty after
reload.

### Files Modified
- `agent/executor.py`
- `agent/learner.py`
- `tests/test_executor.py`
- `tests/test_learner_tools.py`
- `docs/IMPLEMENTATION.md`
