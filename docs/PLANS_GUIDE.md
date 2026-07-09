# Execution Plans Guide

Use execution plans for work too large or risky for chat context alone.

## Create A Plan When

- Multiple commits or sessions expected
- Architectural impact or migration risk
- Staged rollout with validation checkpoints
- Multiple agents/contributors on the same area

**Example candidates for this repo:**

- Docker Compose + integration test suite
- Auth middleware on all graph routes
- Package layout migration (`agent/` → `packages/`)
- Executor write tools with sandbox

## Storage

| Location | Purpose |
| --- | --- |
| `docs/exec-plans/active/` | In-progress plans |
| `docs/exec-plans/completed/` | Finished plans |
| `docs/exec-plans/templates/execution-plan.md` | Starting template |
| `docs/exec-plans/tech-debt-tracker.md` | Deferred cleanup |

## Template Workflow

```bash
# When scripts/ lands from upstream template:
# make new-plan SLUG=docker-compose-stack
```

Until then, copy `templates/execution-plan.md` manually:

```text
docs/exec-plans/active/20260708-docker-compose-stack.md
```

## Expectations

Each plan should state:

1. Goal and scope (in / out)
2. Risks and mitigations
3. Validation commands (e.g. `pytest -m integration`)
4. Progress log with checkboxes
5. Decision log with dates

Archive to `completed/` when done. Update [`QUALITY_SCORE.md`](../QUALITY_SCORE.md)
if the plan materially changes a quality area.
