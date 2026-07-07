# Harness Frontend

React + Vite developer UI for the LangGraph harness (instrument panel).

## Run locally

Terminal 1 — API:

```bash
uvicorn app.main:app --reload --port 8000
```

Terminal 2 — frontend (proxies `/api` → port 8000):

```bash
cd app/frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173

## Build

```bash
cd app/frontend
npm run build
```

Static output: `app/frontend/dist/`

## Keyboard

| Key | Action |
|-----|--------|
| `j` / `k` | Next / previous timeline step |
| `r` | Resume when awaiting human |
