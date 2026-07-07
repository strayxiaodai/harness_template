# Repository Collaboration Guide

Default collaboration model for this agent-first LangGraph harness. Add
stack-specific rules in adjacent docs instead of bloating this file.

## Development Principles

- Prefer boring, legible, well-instrumented technology over opaque complexity.
- Optimize for agent legibility: if important knowledge only exists in chat,
  tickets, or human memory, it effectively does not exist.
- Keep code, docs, tests, config, and release notes synchronized.
- Fix the environment when an agent repeatedly fails; do not rely on prompt
  retries as the main strategy.
- When fixing a bug, check whether tests and docs should be expanded so the
  same class of bug is caught once and stays caught.

## Documentation Discipline

- [`AGENTS.md`](../AGENTS.md) is a routing layer, not a giant policy document.
- [`doc.md`](../doc.md) is the technical encyclopedia for runtime behavior.
- [`docs/`](../docs/) holds process, ops, and quality knowledge.
- [`PRODUCT.md`](../PRODUCT.md) and [`DESIGN.md`](../DESIGN.md) at the repo
  root are the product and visual system of record for the console.
- If behavior changes, update the corresponding docs in the same change.
- Prefer adding a new focused doc over appending unrelated rules to a large
  catch-all file.

## Git And Review

- Keep commits scoped and descriptive.
- Before a commit or PR, verify that docs, examples, and histories reflect the
  final behavior.
- For large or risky work, land changes behind an execution plan checked into
  `docs/exec-plans/`.
- Prefer review comments and follow-up tasks that cite repository files instead
  of private context.

## Testing And Validation

Every meaningful code change should leave behind stronger verification than
before.

| Area | Command |
| --- | --- |
| Python unit tests | `pytest tests/ -q -k "not live"` |
| API smoke | `pytest tests/test_api.py -v` |
| Frontend lint | `cd app/frontend && npm run lint` |
| Frontend build | `cd app/frontend && npm run build` |

Integration tests marked `@pytest.mark.integration` require external services
and are not part of the default local gate yet.

## CI/CD And Release Posture

No GitHub Actions workflows ship with this repo yet. See [`CICD.md`](CICD.md).

When adding pipelines, update `docs/CICD.md` and [`CONTRIBUTING.md`](../CONTRIBUTING.md)
in the same change.

## Configuration Hygiene

- Document environment variables in [`doc.md`](../doc.md).
- Keep `.env` out of version control (see [`.gitignore`](../.gitignore)).
- Avoid hidden setup steps; encode them in versioned markdown or scripts.
