# CI/CD Guide

## Current State

- No workflows under `.github/workflows/`.
- No `Makefile` or `scripts/ci.sh` yet.
- Local validation is manual:

```bash
pytest tests/ -q -k "not live"
cd app/frontend && npm run lint && npm run build
```

## Design Principle

CI/CD should serve the real project instead of preserving placeholder
automation. Start with the smallest real validation path, then add build
artifacts, supply-chain scanning, release, and deployment. Pin new GitHub
Actions to commit SHAs instead of floating tags.

## Recommended Customization Sequence

1. **PR gate** — run `pytest tests/ -q -k "not live"` on every pull request.
2. **Frontend gate** — when `app/frontend/` changes, run `npm run lint` and
   `npm run build`.
3. **Integration job** — after Docker Compose lands, run
   `pytest -m integration`.
4. **Packaging** — add SBOM and provenance after a real release artifact
   exists.
5. **Deploy** — add environment-specific jobs after a target runtime is chosen.

Document all pipeline entry points here when added.

## When Adding CI/CD Back

- Do not restore workflows that only package placeholder metadata.
- If release automation is added, update
  [`SUPPLY_CHAIN_SECURITY.md`](SUPPLY_CHAIN_SECURITY.md) and
  [`releases/README.md`](releases/README.md) in the same change.
