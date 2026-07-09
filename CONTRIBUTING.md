# Contributing

This repository is designed for agent-first development, but the same rules
apply to humans and bots.

## Working Agreement

- Start from [`AGENTS.md`](AGENTS.md), then read the linked docs that match the
  task.
- Keep repository knowledge in versioned files, not only in chat or ticket
  comments.
- If behavior changes, update code, docs, tests, and release/history records
  together.
- For large or risky work, create an execution plan under
  `docs/exec-plans/active/`.

## Before Opening A Pull Request

- Run the checks that match your change:
  - Python: `pytest tests/ -q -k "not live"`
  - Frontend (when touched): `cd app/frontend && npm run lint && npm run build`
- Add or update a history entry if the task changed repository code or workflow.
  See [`docs/HISTORY_GUIDE.md`](docs/HISTORY_GUIDE.md).
- Update release notes when the change is user-visible. See
  [`docs/releases/README.md`](docs/releases/README.md).
- Verify examples in [`README.md`](README.md) and [`docs/IMPLEMENTATION.md`](docs/IMPLEMENTATION.md)
  still match current behavior.

## Review Expectations

- Prefer small, scoped pull requests.
- Call out risks, migrations, and deferred follow-ups explicitly.
- Link to the relevant plan, spec, or history file when context is important.
