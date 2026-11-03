## [2026-10-06 02:50] | Task: Add OpenSpec Explore Skill to Planner

### User Query
> in the agent/planner.py add skills of OpenSpec's explore skill

### Changes Overview
- **Planner Prompt**: Enriched `planner.system` in `config/prompts.yaml` with the OpenSpec Explore thinking partner stance:
  - Thinking Partner: Explore context and problem space, map existing codebase conventions before prescribing mutations.
  - Surface Assumptions: Identify hidden assumptions, edge cases, invariants, and potential breaking changes.
  - Evaluate Trade-offs: Document trade-off decisions explicitly in the plan rationale.
  - Spec-Driven Verification: Define unambiguous "done-when" criteria for each step.
- **Planner Node**: Updated [`agent/planner.py`](file:///Users/frank/harness_template/agent/planner.py) to incorporate OpenSpec Explore directives and docstrings into the prompt construction.
- **Skill Playbook**: Added a formal [`app/skills/openspec-explore/SKILL.md`](file:///Users/frank/harness_template/app/skills/openspec-explore/SKILL.md) and metadata to the skills library for discovery and runtime attachment, fully documenting OpenSpec's 6 core stances (*Curious*, *Open threads*, *Visual*, *Adaptive*, *Patient*, *Grounded*) and change-planning rules (*Follow dependencies*, *Surface assumptions*, *Grounded recommendations*).
- **Tests**: Added `test_planner_includes_openspec_explore_stance` in [`tests/test_planner.py`](file:///Users/frank/harness_template/tests/test_planner.py).

### Design Intent
OpenSpec Explore operates on the principle of "thinking partner, not premature implementer". By weaving these principles into the planner's prompt and providing an on-disk skill playbook, the planner systematically explores the problem space, questions assumptions, weighs trade-offs, and produces spec-driven steps with explicit verification criteria.

### Files Modified
- `config/prompts.yaml`
- `agent/planner.py`
- `app/skills/openspec-explore/SKILL.md`
- `app/skills/openspec-explore/harness.json`
- `tests/test_planner.py`
