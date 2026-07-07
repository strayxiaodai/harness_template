# Supply Chain Security

Supply-chain posture for this Python + Node harness.

## Current State

- No GitHub Actions supply-chain scanning or release provenance workflows.
- Python dependencies in `requirements*.txt` and [`pyproject.toml`](../pyproject.toml).
- Frontend lockfile: `app/frontend/package-lock.json`.

Defaults:

- Do not commit secrets, tokens, or local private configuration.
- Commit lockfiles for reproducible installs.
- Pin new GitHub Actions to immutable commit SHAs instead of floating tags.

## Tooling To Add Later

- `actions/dependency-review-action` — PR dependency changes
- `google/osv-scanner-action` — known vulnerability scan
- `anchore/sbom-action` — SPDX SBOM artifact
- `actions/attest-build-provenance` — signed build provenance

## Python Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt       # pytest
pip install -r requirements-rag.txt      # optional cross-encoder
pip install -r requirements-postgres.txt # optional pgvector
pip install -e ".[mcp]"                  # optional MCP client
```

## When The Project Ships Releases

- Add ecosystem lockfiles and keep them committed.
- Make builds deterministic and produce explicit versioned artifacts.
- Gate production deployment on provenance verification when possible.
- Update [`CICD.md`](CICD.md) and [`releases/README.md`](releases/README.md)
  in the same change.
