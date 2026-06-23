# Design System — Harness Console

## Mood

Late-night lab bench — phosphor trace on matte black, amber interrupt lamps.

## Color strategy

Restrained. Dark pure-near-black surfaces; cyan carries active trace; amber reserved for HITL interrupt only.

## Palette (OKLCH)

| Token | Value | Role |
|-------|-------|------|
| `--bg` | `oklch(0.09 0.008 220)` | App background |
| `--surface` | `oklch(0.13 0.012 220)` | Panels, sidebars |
| `--surface-raised` | `oklch(0.16 0.014 220)` | Inputs, nested regions |
| `--ink` | `oklch(0.92 0.01 220)` | Primary text |
| `--muted` | `oklch(0.68 0.015 220)` | Secondary labels |
| `--primary` | `oklch(0.72 0.14 195)` | Active node, primary actions |
| `--primary-on` | `oklch(0.98 0 0)` | Text on primary fills |
| `--accent` | `oklch(0.78 0.16 75)` | HITL interrupt, warnings |
| `--accent-on` | `oklch(0.12 0 0)` | Text on accent fills |
| `--success` | `oklch(0.65 0.14 150)` | Approved / complete |
| `--border` | `oklch(0.28 0.02 220)` | Dividers, panel edges |
| `--focus-ring` | `oklch(0.72 0.14 195)` | Focus-visible outline |

## Typography

- **UI:** `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`
- **Data:** `"JetBrains Mono", "SF Mono", ui-monospace, monospace`
- **Scale (rem):** 0.75 / 0.8125 / 0.875 / 1 / 1.125 / 1.25
- Body max measure for prose: 70ch

## Layout

- Three-column shell ≥ 1024px: command 240px · center flex · inspector 320px
- `< 1024px`: stack command → spine → timeline → inspector
- Spacing scale: 4 / 8 / 12 / 16 / 24 / 32px
- Panel radius: 12px max; buttons 8px; pills full-round

## Motion

- Active node pulse: 180ms ease-out; disabled under `prefers-reduced-motion`
- No page-load choreography

## Z-index

| Layer | Value |
|-------|-------|
| dropdown | 10 |
| sticky bar | 20 |
| toast | 40 |
| skip link | 50 |
