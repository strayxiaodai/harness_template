# Harness Console

Developer console for the LangGraph harness (React + Vite).

## Run locally

Terminal 1 — API:

```bash
uvicorn api.server:api --reload --port 8000
```

Terminal 2 — console (proxies `/api` → port 8000):

```bash
cd console
npm install
npm run dev
```

Open http://127.0.0.1:5173

## Build

```bash
cd console
npm run build
```

Static output: `console/dist/`

## Keyboard

| Key | Action |
|-----|--------|
| `j` / `k` | Next / previous timeline step |
| `r` | Resume when awaiting human |
