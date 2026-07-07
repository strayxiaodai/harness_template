# Frontend Guide

Harness developer console under `app/frontend/`.

## Stack

- React 19 + TypeScript
- Vite 8 dev server (port `5173`)
- CSS tokens in `src/styles/tokens.css`
- API client in `src/lib/api.ts`

## Local Development

```bash
# Terminal 1 — API
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd app/frontend
npm install
npm run dev
```

CORS allows `http://localhost:5173` and `http://127.0.0.1:5173` (see
`app/core/config.py`).

## Build And Lint

```bash
cd app/frontend
npm run lint
npm run build
npm run preview   # preview production build
```

## Component Boundaries

| Component | Role |
| --- | --- |
| `CommandColumn` | Task input, run/resume controls, skill picker |
| `GraphSpine` | LangGraph node spine and round status |
| `TraceTimeline` | Per-node event timeline |
| `InspectorStack` | Expandable payloads (plan, tools, review, RAG) |
| `StatusBar` | Backend health and capability indicators |

The frontend talks to the API only — no direct LangGraph or Python imports.

## Design System

Follow [`DESIGN.md`](../DESIGN.md) for palette, typography, and layout rules.
Product constraints are in [`PRODUCT.md`](../PRODUCT.md).

## Testing Strategy (current)

- **Lint:** `npm run lint` (ESLint)
- **Build:** `npm run build` (TypeScript + Vite)
- **Browser verification:** manual against local API
- **Automated UI tests:** not yet implemented

## Known Gaps

- Frontend is not served by FastAPI; dev requires two processes.
- No thread list UI endpoint on the API yet.
- Audit rows require Postgres; UI should signal when audit is unavailable.
