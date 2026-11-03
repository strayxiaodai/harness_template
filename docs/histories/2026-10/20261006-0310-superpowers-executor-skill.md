## [2026-10-06 03:10] | Task: Integrate Superpowers Skill into Executor Node

### User Query
> use superpowers skill in agent/executor.py stage

### Changes Overview
- **Executor System Prompt**: Enriched `executor.system` and `executor.summarize` in [`config/prompts.yaml`](file:///Users/frank/harness_template/config/prompts.yaml) with Superpowers execution mandates:
  - *The Plan Did The Thinking*: Follow the plan task-by-task; do not drift or skip steps.
  - *Evidence Over Claims*: Require tool evidence and verification test results before declaring work complete.
  - *TDD & Verification Gate*: Enforce verifiable test execution and writing deterministic Python scripts under `scripts/`.
  - *Rulings, Not Stalls*: Explicitly record rulings for minor plan defects (`Ruling: <what> — <why> — <cost if wrong>`) rather than guessing or stalling.
- **Executor Node**: Updated [`agent/executor.py`](file:///Users/frank/harness_template/agent/executor.py) (both native Pydantic AI and legacy tool loop paths) to inject the Superpowers execution directive into prompt construction.
- **Skill Playbook**: Added a formal [`app/skills/superpowers-executing/SKILL.md`](file:///Users/frank/harness_template/app/skills/superpowers-executing/SKILL.md) and provenance in [`harness.json`](file:///Users/frank/harness_template/app/skills/superpowers-executing/harness.json) to the skills library for discovery and optional explicit attachment.
- **Tests**: Added `test_executor_includes_superpowers_execution_directives` in [`tests/test_executor_pydantic_ai.py`](file:///Users/frank/harness_template/tests/test_executor_pydantic_ai.py).

### Design Intent
Adopt the disciplined execution philosophy of `obra/superpowers` (`executing-plans` and `test-driven-development`) to keep the executor focused, evidence-backed, and methodically tied to the planner's output.

### Files Modified
- `config/prompts.yaml`
- `agent/executor.py`
- `app/skills/superpowers-executing/SKILL.md`
- `app/skills/superpowers-executing/harness.json`
- `tests/test_executor_pydantic_ai.py`
