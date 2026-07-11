# Console Layout Density Rebalance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebalance the harness console so Inspector · Center · Command has even density, the center owns the viewport, and Command is regrouped on the right.

**Architecture:** Flatten `app-main` children and drive desktop/narrow placement with CSS `grid-template-areas` (no center wrapper). Regroup `CommandColumn` into Run / Skills / HITL / Distill sections. Tighten spine/timeline/inspector CSS so panels share chrome and the timeline fills leftover height. Update `DESIGN.md` / `FRONTEND.md` to match.

**Tech Stack:** React 19 + Vite + CSS custom properties (`tokens.css` / `global.css`). No new dependencies. Verification via `npm run build` + visual smoke (no frontend unit-test runner in this package).

**Spec:** [`docs/superpowers/specs/2026-07-10-console-layout-density-design.md`](../specs/2026-07-10-console-layout-density-design.md)

---

## File map

| File | Responsibility |
|------|----------------|
| `app/frontend/src/App.tsx` | DOM order: Inspector, GraphSpine, TraceTimeline, Command |
| `app/frontend/src/App.css` | Grid areas, widths `300px · 1fr · 220px`, narrow stack |
| `app/frontend/src/styles/global.css` | Shared `.panel` padding if missing |
| `app/frontend/src/components/CommandColumn.tsx` | Section regroup + hint trim |
| `app/frontend/src/components/CommandColumn.css` | Section chrome, HITL accent block |
| `app/frontend/src/components/GraphSpine.css` | Denser chips |
| `app/frontend/src/components/TraceTimeline.css` | Fill height; keep 1px selected border |
| `app/frontend/src/components/InspectorStack.tsx` | Idle empty state |
| `app/frontend/src/components/InspectorStack.css` | Match panel padding |
| `docs/DESIGN.md` | Layout order + widths |
| `docs/FRONTEND.md` | Layout diagram + StatusBar position fix |
| `docs/histories/2026-07/…` | History entry after code lands |

---

### Task 1: Shell grid — DOM order + areas

**Files:**
- Modify: `app/frontend/src/App.tsx`
- Modify: `app/frontend/src/App.css`

- [ ] **Step 1: Flatten `app-main` children in `App.tsx`**

Replace the center wrapper so the four regions are direct children, in this DOM order:

```tsx
<main className="app-main" id="main-content">
  <InspectorStack step={selectedStep} accumulated={accumulated} />
  <GraphSpine
    activeNode={activeNode}
    completedNodes={completedNodes}
    refineFrom={refineFrom}
    onSelectNode={handleSelectNode}
  />
  <TraceTimeline
    steps={timeline}
    selectedId={selectedStepId}
    activeNode={activeNode}
    onSelect={selectStep}
  />
  <CommandColumn
    /* existing props unchanged */
  />
</main>
```

Remove the `<div className="app-center">` wrapper and delete unused `.app-center` rules in `App.css` after Step 2.

- [ ] **Step 2: Rewrite `.app-main` grid in `App.css`**

```css
.app-main {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr) 220px;
  grid-template-rows: auto minmax(0, 1fr);
  grid-template-areas:
    "inspector spine command"
    "inspector timeline command";
  gap: var(--space-3);
  flex: 1;
  min-height: 0;
  padding: var(--space-3);
  padding-left: max(var(--space-3), env(safe-area-inset-left, 0));
  padding-right: max(var(--space-3), env(safe-area-inset-right, 0));
}

.inspector-stack {
  grid-area: inspector;
}

.graph-spine {
  grid-area: spine;
}

.trace-timeline {
  grid-area: timeline;
}

.command-column {
  grid-area: command;
}

@media (max-width: 1023px) {
  .app-main {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
    grid-template-areas:
      "spine"
      "timeline"
      "inspector"
      "command";
  }

  .inspector-stack {
    max-height: min(480px, 50dvh);
  }
}
```

Keep existing smaller-breakpoint padding rules; drop obsolete `.app-center` and the old `grid-template-columns: 240px … 320px`.

- [ ] **Step 3: Verify TypeScript build**

Run: `cd app/frontend && npm run build`  
Expected: exit 0 (tsc + vite build succeed).

- [ ] **Step 4: Commit**

```bash
git add app/frontend/src/App.tsx app/frontend/src/App.css
git commit -m "Reorder console shell to inspector · center · command."
```

---

### Task 2: Command column regroup

**Files:**
- Modify: `app/frontend/src/components/CommandColumn.tsx`
- Modify: `app/frontend/src/components/CommandColumn.css`

- [ ] **Step 1: Restructure JSX body into four sections**

Inside `.command-column__body`, use this order and structure (preserve all existing handlers/props; only rearrange markup and defaults):

1. **Run** — always visible block (`div.command-section.command-section--run`):
   - Task textarea + one short hint
   - Plan textarea
   - Max rounds row
   - Actions: Start thread, New thread only (move Resume out)

2. **Skills** — `<details className="skill-library">` **without** `open={!isNarrow}` (always start collapsed). Keep existing skill picker / Run skill / preview content. Place **after** Run.

3. **HITL** — `div.command-section.command-section--hitl` (add `--active` when `phase === 'awaiting_human'`):
   - HITL checkbox (keep)
   - Remove the long “Enable HITL to step through…” paragraph
   - When `canResume && phase === 'awaiting_human'`: show Continue button (`btn-accent`), `OverrideForm`, and `ClarificationForm` (move from bottom of column)

4. **Distill** — keep `<details className="skill-distill" open={!isNarrow && canDistill}>` as today.

5. Keep the error alert block at the end of the body.

Task hint text (replace current long hint):

```tsx
<p id="task-hint" className="command-column__hint">
  Required for Start thread. Optional when running a saved skill.
</p>
```

Skills `open` attribute: omit `open` entirely (collapsed by default on all viewports).

- [ ] **Step 2: Add section styles in `CommandColumn.css`**

```css
.command-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface-raised);
}

.command-section__label {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: var(--muted);
}

.command-section--hitl.command-section--active {
  border-color: var(--accent);
  background: color-mix(in oklch, var(--accent) 8%, var(--surface-raised));
}

.skill-library,
.skill-distill {
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  padding: 0;
  margin: 0;
  background: var(--surface-raised);
}

.skill-library__summary,
.skill-distill__summary {
  padding: 0 var(--space-3);
}

.skill-library__body,
.skill-distill__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: 0 var(--space-3) var(--space-3);
}
```

Remove obsolete rules that assumed Skills sat above Task with only a bottom border divider (old `.skill-library { border-bottom… }` block), replacing with the rules above.

- [ ] **Step 3: Build**

Run: `cd app/frontend && npm run build`  
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add app/frontend/src/components/CommandColumn.tsx app/frontend/src/components/CommandColumn.css
git commit -m "Regroup command column into Run, Skills, HITL, Distill."
```

---

### Task 3: Center + inspector density

**Files:**
- Modify: `app/frontend/src/components/TraceTimeline.css`
- Modify: `app/frontend/src/components/GraphSpine.css`
- Modify: `app/frontend/src/components/InspectorStack.tsx`
- Modify: `app/frontend/src/components/InspectorStack.css`
- Modify: `app/frontend/src/styles/global.css`

- [ ] **Step 1: Let timeline fill height**

In `TraceTimeline.css`, change `.trace-timeline__list` so it grows instead of capping at 320px:

```css
.trace-timeline__list {
  margin: 0;
  padding: var(--space-2);
  list-style: none;
  overflow: auto;
  flex: 1;
  min-height: 0;
  /* remove max-height: 320px */
}
```

Keep `.trace-row--selected` as full 1px `border-color: var(--primary)` + `background: var(--surface-raised)` (already correct — do not add a side stripe). Optionally tighten row padding to `var(--space-2) var(--space-3)` if rows feel tall; keep `min-height` at least 36px.

- [ ] **Step 2: Denser spine chips**

In `GraphSpine.css`:

```css
.graph-spine__nodes {
  gap: var(--space-2);
}

.graph-node {
  gap: var(--space-1);
  min-height: 36px;
  padding: var(--space-1) var(--space-3);
}
```

Leave active/done/HITL color rules unchanged.

- [ ] **Step 3: Shared panel padding + inspector idle empty**

In `global.css`, ensure `.panel` has consistent padding for titles:

```css
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-panel);
}

.panel-title {
  margin: 0;
  padding: var(--space-3) var(--space-4) var(--space-2);
  /* existing font rules */
}
```

(If `CommandColumn` / inspector already pad titles differently, prefer moving title padding into `.panel-title` once and removing duplicate padding from section bodies only where it double-pads.)

In `InspectorStack.tsx`, add a compact idle state when there is no selected step and the accumulated snapshot has no plan/execution/review/tool_calls/result:

```tsx
function isSparseSnapshot(state: AgentStateSnapshot): boolean {
  return (
    !state.plan?.length &&
    !state.execution &&
    !state.tool_calls?.length &&
    !state.review &&
    !state.result
  )
}

export function InspectorStack({ step, accumulated }: InspectorStackProps) {
  if (!step && isSparseSnapshot(accumulated)) {
    return (
      <aside className="inspector-stack panel" aria-label="Inspector">
        <h2 className="panel-title">Inspector</h2>
        <p className="empty-state">Select a timeline step</p>
      </aside>
    )
  }
  const state = step?.state ?? accumulated
  // existing sections…
}
```

In `InspectorStack.css`, ensure `.inspector-stack` uses the same border/radius as other columns when it is the grid cell (either `className="inspector-stack panel"` on the aside always, or border on `.inspector-stack` matching `.panel`). Avoid nested double borders on each `inspector-section` if the outer aside becomes the single panel — prefer: outer scroll container without double chrome; keep per-section `.panel` as today if that already matches command. Goal: no tall hollow void on idle.

- [ ] **Step 4: Build**

Run: `cd app/frontend && npm run build`  
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add app/frontend/src/components/TraceTimeline.css \
  app/frontend/src/components/GraphSpine.css \
  app/frontend/src/components/InspectorStack.tsx \
  app/frontend/src/components/InspectorStack.css \
  app/frontend/src/styles/global.css
git commit -m "Tighten center and inspector density for even panel rhythm."
```

---

### Task 4: Docs + history

**Files:**
- Modify: `docs/DESIGN.md`
- Modify: `docs/FRONTEND.md`
- Create: `docs/histories/2026-07/20260710-2355-console-layout-density.md` (adjust time if needed)

- [ ] **Step 1: Update `docs/DESIGN.md` Layout section**

Replace layout bullets and ASCII with:

```markdown
## Layout

- Three-column shell ≥ 1024px: inspector 300px · center flex · command 220px
- `< 1024px`: stack spine → timeline → inspector → command
- Spacing scale: 4 / 8 / 12 / 16 / 24 / 32px
- Panel radius: 12px max; buttons 8px; pills full-round

```text
┌──────────────────────────────────────────────────────────┐
│ StatusBar                                                │
├──────────────┬───────────────────────────┬───────────────┤
│ Inspector    │ GraphSpine + TraceTimeline│ CommandColumn │
│  (300px)     │      (flex)               │  (220px)      │
├──────────────┴───────────────────────────┴───────────────┤
│ Footer shortcuts                                         │
└──────────────────────────────────────────────────────────┘
```
```

- [ ] **Step 2: Update `docs/FRONTEND.md` Layout section**

Fix the diagram to StatusBar on top, order Inspector · Center · Command, widths 300 / flex / 220, and narrow stack note. Remove the incorrect “StatusBar spans the bottom” wording (StatusBar is top; footer holds shortcuts).

- [ ] **Step 3: History entry**

Create `docs/histories/2026-07/20260710-2355-console-layout-density.md` per `docs/HISTORY_GUIDE.md` / `docs/histories/template.md`: user request (refine ugly layout / density), approach B + command-right, key files touched.

- [ ] **Step 4: Commit**

```bash
git add docs/DESIGN.md docs/FRONTEND.md docs/histories/2026-07/20260710-2355-console-layout-density.md
git commit -m "Document console layout density rebalance."
```

- [ ] **Step 5: Visual smoke (manual)**

With API + `npm run dev` running:

1. Desktop ≥1024: columns are Inspector | spine/timeline | Command at ~300 / flex / 220.
2. Idle: Skills and Distill collapsed; Run open; inspector shows “Select a timeline step”.
3. Timeline area is tall under the spine (not capped at ~320px).
4. Narrow &lt;1024: order spine → timeline → inspector → command.
5. HITL interrupt: amber HITL section + Continue; `r` still resumes.

- [ ] **Step 6: Graphify update (workspace rule)**

Run: `graphify update .`  
Expected: graph refresh completes without error.

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Grid `300 · 1fr · 220`, Inspector · Center · Command | Task 1 |
| Narrow spine → timeline → inspector → command | Task 1 |
| Command regroup Run / Skills / HITL / Distill | Task 2 |
| Skills collapsed by default; below Run | Task 2 |
| HITL amber + Resume on interrupt | Task 2 |
| Timeline fills height | Task 3 |
| Denser spine; selected row 1px border | Task 3 |
| Inspector short empty state | Task 3 |
| DESIGN.md / FRONTEND.md | Task 4 |
| No palette / StatusBar redesign | Honored (out of scope) |
