# Enterprise LangGraph Harness

A production-oriented LangGraph harness with a Plan → Do → Check → Action agent
loop, RAG memory, FastAPI serving, a React developer console, MCP tool
integration, and skill distillation.

Methodology and collaboration patterns are adapted from
[iFurySt/harness-template](https://github.com/iFurySt/harness-template).

## Quick Start

### API (Python 3.12+)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Local dev uses **SQLite** checkpoints by default at
`data/checkpoints/langgraph.db`.

```bash
curl http://localhost:8000/health
```

### Frontend (optional console)

```bash
cd app/frontend
npm install
npm run dev
```

The UI expects the API at `http://localhost:8000` and runs on port `5173`.

### Tests

```bash
pytest tests/ -q -k "not live"
```

## Documentation Map

| Doc | Purpose |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Agent entry point and doc routing |
| [`docs/IMPLEMENTATION.md`](docs/IMPLEMENTATION.md) | Full technical implementation (API, RAG, config, schemas) |
| [`docs/PRODUCT.md`](docs/PRODUCT.md) | Product purpose, users, and UX principles |
| [`docs/DESIGN.md`](docs/DESIGN.md) | Harness console design system |
| [`docs/`](docs/) | Collaboration, architecture, quality, and ops guides |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | PR and change expectations |

## Environment

Set LLM credentials before running agent threads:

```bash
export LLM_PROVIDER=openai   # openai | anthropic | ollama
export OPENAI_API_KEY=...
```

Optional Postgres checkpoints, audit logging, and pgvector memory:

```bash
pip install -r requirements-postgres.txt
export CHECKPOINT_BACKEND=postgres
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/agents
```

See [`docs/IMPLEMENTATION.md`](docs/IMPLEMENTATION.md) for the full implementation guide.

## License

[MIT](LICENSE)
