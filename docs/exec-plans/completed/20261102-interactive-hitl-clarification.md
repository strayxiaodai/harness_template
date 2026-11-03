# Interactive Click-to-Confirm HITL for All Nodes

## Goal

Upgrade Human-in-the-Loop (HITL) execution so that each node (`planner`, `executor`, `learner`, `actioner`) presents structured, interactive decision cards with clickable options and recommended choices, enabling operators to inspect and confirm execution in one click.

## Scope

- In scope:
  - Enrich `ClarificationQuestion` schema with `options`, `default`, and `is_multi_select`.
  - Update `agent/clarification.py` to normalize options, defaults, and answers.
  - Wire interactive HITL clarification into `agent/planner.py`, `agent/executor.py`, `agent/learner.py`, and `agent/actioner.py`.
  - Update React frontend (`app/frontend/src/types/api.ts`, `app/frontend/src/lib/clarification.ts`, `app/frontend/src/components/Workplace.tsx`, CSS) with interactive option chips and click-to-confirm UX.
  - Unit tests covering question creation, options serialization, and resume resolution.
- Out of scope:
  - Modifying checkpointer backends (SQLite/Postgres).
  - Modifying RAG vector stores.

## Context

- Relevant docs:
  - `docs/ARCHITECTURE.md`
  - `docs/IMPLEMENTATION.md`
  - `docs/FRONTEND.md`
- Relevant code:
  - `graph/schemas.py`
  - `agent/clarification.py`
  - `agent/planner.py`
  - `agent/executor.py`
  - `agent/learner.py`
  - `agent/actioner.py`
  - `app/frontend/src/`

## Risks & Mitigations

- Risk: Node tests might block if mocked LLMs or test runs enable HITL unexpectedly.
  - Mitigation: Default `human_in_the_loop` to `False` in tests, only activate in dedicated HITL test cases.
- Risk: Backward compatibility with plain text clarification answers in CLI/curl.
  - Mitigation: If `interrupt_resume` contains plain text or missing fields, fallback gracefully to `question.default`.

## Milestones

1. Extend `ClarificationQuestion` schema and `agent/clarification.py` helpers.
2. Wire interactive questions into `planner.py`, `executor.py`, `learner.py`, and `actioner.py`.
3. Update frontend types, `useResumeDraft`, `Workplace.tsx`, and CSS styles.
4. Add unit tests and verify entire test suite passes.

