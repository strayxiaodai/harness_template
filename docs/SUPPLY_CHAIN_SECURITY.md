# Supply Chain Security

Supply-chain posture for this Python + Node harness.

## Current State

| Asset | Location | Committed? |
| --- | --- | --- |
| Python deps | `requirements*.txt`, `pyproject.toml` | Yes |
| Frontend lockfile | `app/frontend/package-lock.json` | Yes |
| GitHub Actions | None yet | — |
| SBOM / provenance | None yet | — |

Defaults:

- Never commit `.env`, API keys, or `mcp/servers.json` with secrets
- Commit lockfiles for reproducible installs
- Pin GitHub Actions to immutable SHAs (see [`CICD.md`](CICD.md))

## Install Surfaces

```bash
# Core
pip install -r requirements.txt

# Dev / test
pip install -r requirements-dev.txt

# Optional
pip install -r requirements-rag.txt
pip install -r requirements-postgres.txt
pip install -e ".[mcp]"

# Frontend
cd app/frontend && npm ci
```

**Example — verify lockfile present before PR:**

```bash
test -f app/frontend/package-lock.json && pip freeze | head
```

## Tooling To Add With CI

| Tool | Purpose |
| --- | --- |
| `actions/dependency-review-action` | PR dependency diff review |
| `google/osv-scanner-action` | Known CVE scan |
| `anchore/sbom-action` | SPDX SBOM artifact |
| `actions/attest-build-provenance` | Signed release provenance |

## Python Optional Extras

Declared in `pyproject.toml`:

```toml
[project.optional-dependencies]
rerank = ["sentence-transformers"]
postgres = ["psycopg[binary]", "psycopg_pool", "pgvector", ...]
dev = ["httpx", "pytest", "pytest-asyncio"]
mcp = ["mcp"]
```

Only install extras needed for your environment to reduce attack surface.

## When Shipping Releases

1. Deterministic builds with locked dependencies
2. Versioned artifacts (wheel, frontend `dist/`)
3. Provenance verification before production deploy
4. Update [`CICD.md`](CICD.md) and [`releases/README.md`](releases/README.md)

## Related

- Secrets handling: [`SECURITY.md`](SECURITY.md)
- CI rollout plan: [`CICD.md`](CICD.md)
