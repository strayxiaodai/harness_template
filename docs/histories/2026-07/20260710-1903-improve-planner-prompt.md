## [2026-07-10 19:03] | Task: Improve planner system prompt

### Execution Context

- Agent ID: `Auto`
- Base Model: `Composer`
- Runtime: `Cursor`

### User Query

> Distill planning/execution skills into prompts; raise all prompts to ≥ 4.5/5; then search online for best public skills and distill them into `config/prompts.yaml`.

### Changes Overview

- Area: agent / RAG / skill prompts
- Key actions:
  - Iterated planner/executor/reviewer/actioner/rag/skills prompts for schema fit.
  - Online distill into prompts from:
    - [bluriesophos/cursorskills](https://github.com/bluriesophos/cursorskills) `battle-plan`, `pre-mortem`, `prove-it`, `loose-ends`
    - [Anthropic skill-creator](https://github.com/anthropics/skills) progressive disclosure + pushy `description`
    - Cursor / agentskills.io guidance (short always-on prompts; skills for workflows)

### Design Intent

Borrow process patterns only; keep harness role splits and `PlanResult` /
`ExecutorResult` / `ReviewResult` / `ActionScoreResult` / `SkillDraft` contracts.
Skip human-confirmation gates and parallel-subagent review (wrong product layer).

### Self-score (target ≥ 4.5 each)

| Prompt | Avg | Main lift from research |
| --- | --- | --- |
| `planner.system` | 4.7 | battle-plan scope + pre-mortem reorder |
| `executor.system` | 4.6 | prove-it observe; loose-ends honesty |
| `executor.summarize` | 4.6 | unable-to-verify over fake confidence |
| `reviewer.system` | 4.8 | adversarial proof + loose ends |
| `actioner.system` | 4.6 | penalize missing verification |
| `rag.rewrite` | 4.7 | retrieval-friendly phrasing |
| `rag.extract` | 4.5 | empty-over-clutter |
| `skills.distill` | 4.7 | pushy description + progressive disclosure |

### Files Modified

- `config/prompts.yaml`
- `docs/histories/2026-07/20260710-1903-improve-planner-prompt.md`
