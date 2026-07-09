# CI/CD Guide

## Current State

- No workflows under `.github/workflows/`.
- No `Makefile` or `scripts/ci.sh`.
- Local validation (manual):

```bash
# Python
pytest tests/ -q -k "not live"

# Frontend (when touched)
cd app/frontend && npm run lint && npm run build
```

## Design Principle

CI should run **real** project checks, not placeholder metadata packaging.
Pin GitHub Actions to commit SHAs, not floating tags.

## Recommended Rollout

| Phase | What to add | Doc to update |
| --- | --- | --- |
| 1 | PR pytest gate | This file, `CONTRIBUTING.md` |
| 2 | Frontend lint/build on `app/frontend/**` changes | `FRONTEND.md` |
| 3 | `pytest -m integration` after Docker Compose | `IMPLEMENTATION.md`, `RELIABILITY.md` |
| 4 | SBOM + dependency review | `SUPPLY_CHAIN_SECURITY.md` |
| 5 | Deploy job | `ARCHITECTURE.md`, `releases/` |

## Example — minimal PR workflow (not yet committed)

Save as `.github/workflows/test.yml` when ready:

```yaml
name: test
on:
  pull_request:
  push:
    branches: [main]

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest tests/ -q -k "not live"

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: app/frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: app/frontend/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run build
```

Replace `@v4` / `@v5` with pinned SHAs before production use.

## Path Filters (optional)

```yaml
on:
  pull_request:
    paths:
      - "app/frontend/**"
```

Use for frontend-only jobs to save CI minutes.

## When Adding CI/CD

- Do not restore workflows that only package placeholder metadata.
- Update [`SUPPLY_CHAIN_SECURITY.md`](SUPPLY_CHAIN_SECURITY.md) when adding scans.
- Update [`releases/README.md`](releases/README.md) when adding release automation.
- Document the canonical local command here so agents and humans use the same gate.

**Example — after CI lands, contributors run:**

```bash
pytest tests/ -q -k "not live"   # same as CI python job
```
