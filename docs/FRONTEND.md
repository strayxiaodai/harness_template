# Frontend Guide

Harness developer console under `app/frontend/`. Built as an **instrument
panel** for the graph loop — not a chat UI. See [`PRODUCT.md`](PRODUCT.md)
and [`DESIGN.md`](DESIGN.md).

## Stack

| Piece | Location |
| --- | --- |
| React 19 + TypeScript | `src/` |
| Vite 8 dev server | port `5173` |
| Design tokens | `src/styles/tokens.css` |
| API client | `src/lib/api.ts` |
| Console state machine | `src/hooks/useConsole.ts` |

## Local Development

```bash
# Terminal 1 — API
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd app/frontend
npm install
npm run dev
# → http://localhost:5173
```

### API proxy

Vite rewrites `/api/*` → `http://127.0.0.1:8000/*`:

```typescript
// vite.config.ts
proxy: {
  '/api': {
    target: 'http://127.0.0.1:8000',
    rewrite: (path) => path.replace(/^\/api/, ''),
  },
}
```

Frontend calls `fetch('/api/run')`; FastAPI sees `POST /run`.

**Example — verify proxy:**

```bash
curl -s http://localhost:5173/api/health
# {"status":"ok"}
```

CORS on the API allows `localhost:5173` for direct calls; the proxy avoids CORS
during normal dev.

## Build And Lint

```bash
cd app/frontend
npm run lint      # ESLint
npm run build     # tsc + vite build
npm run preview   # serve production build locally
```

## Layout (three-column shell)

From [`DESIGN.md`](DESIGN.md): inspector · center spine/timeline · command.
`StatusBar` spans the top; footer holds keyboard shortcuts.

```text
┌──────────────────────────────────────────────────────────┐
│ StatusBar — health, rounds, skill eligibility            │
├──────────────┬───────────────────────────┬───────────────┤
│ Inspector    │ GraphSpine + TraceTimeline│ CommandColumn │
│  (280px)     │      (flex)               │  (268px)      │
├──────────────┴───────────────────────────┴───────────────┤
│ Footer shortcuts                                         │
└──────────────────────────────────────────────────────────┘
```

Narrow (&lt;1024px): spine → timeline → inspector → command.

## Components

| Component | Role | Key hooks / data |
| --- | --- | --- |
| `CommandColumn` | Task, plan, max rounds, HITL toggle, run/resume, skill picker | `useConsole`, `useSkills` |
| `GraphSpine` | Five nodes: planner → executor → reviewer → actioner → memorize | `GRAPH_NODES`, `completedNodes`, `activeNode` |
| `TraceTimeline` | Chronological step list from stream | `timeline`, `selectStep` |
| `InspectorStack` | Expandable payloads for selected step | `plan`, `execution`, `review`, `tool_calls`, `memory_context` |
| `StatusBar` | API health, round counter, errors | `useHealth`, `runResponse` |

The frontend talks to the API only — no LangGraph or Python imports.

## API ↔ UI Data Flow

**Run (auto mode):**

```text
CommandColumn [Run]
  → postStreamRun() or postRun()
  → SSE chunks update timeline + accumulated state
  → final RunResponse → StatusBar (rounds, skill_eligible)
```

**HITL mode:**

```text
Run with human_in_the_loop: true
  → stream pauses when status === "awaiting_human"
  → GraphSpine shows next_action as pending
  → [Resume] → postResume()
```

**Skill workflow:**

```text
List skills     → GET /api/skills
Run with skill  → POST /api/run { skill_slug }
Distill preview → POST /api/skills/distill { save: false }
Save skill      → POST /api/skills/save
```

**Example — skill eligibility in UI:**

`RunResponse.skill_eligible === false` shows `skill_ineligible_reason` in the
command column (e.g. "Loop quality score must be at least 80…"). Logic mirrored
in `src/lib/skillEligibility.ts`.

## Type Alignment

TypeScript types in `src/types/api.ts` mirror backend Pydantic models in
`app/schemas/`. When API schemas change, update both sides and
[`IMPLEMENTATION.md`](IMPLEMENTATION.md).

**Example — shared shape:**

```typescript
interface RunResponse {
  status: 'complete' | 'awaiting_human'
  skill_eligible: boolean
  skill_ineligible_reason: string | null
  // ...
}
```

## Design System

- Tokens: `src/styles/tokens.css` (must match [`DESIGN.md`](DESIGN.md) OKLCH palette)
- **Cyan** — active node / primary actions
- **Amber** — HITL interrupt / warnings only
- Monospace for JSON payloads in inspector panels

## Keyboard And Accessibility

Target WCAG 2.1 AA per product spec:

- Run, resume, and step selection keyboard-operable
- Visible focus rings (`--focus-ring` token)
- `prefers-reduced-motion` respected in `App.css`

## Testing Strategy

| Check | Command |
| --- | --- |
| Lint | `npm run lint` |
| Typecheck + build | `npm run build` |
| Manual smoke | Run + HITL resume against local API |
| Automated UI tests | Not implemented yet |

**Example — PR frontend gate:**

```bash
cd app/frontend && npm run lint && npm run build
```

## Known Gaps

| Gap | Workaround |
| --- | --- |
| Frontend not served by FastAPI | Run Vite dev server alongside API |
| No thread list API | Operator supplies `thread_id` manually |
| No audit panel | Postgres audit not exposed via HTTP yet |
| SSE only during active stream | Use curl `/stream` for headless debugging |

See [`exec-plans/tech-debt-tracker.md`](exec-plans/tech-debt-tracker.md).
