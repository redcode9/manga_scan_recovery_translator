# msrt-desktop

Local web UI for `msrt`. Talks to the FastAPI backend exposed by
`uv run msrt ui` at `http://127.0.0.1:4001`.

## Quick start (development)

```bash
# 1) Backend (in one terminal, from the repo root)
uv run msrt ui

# 2) Frontend (in another terminal)
cd apps/desktop
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). The Vite dev
server proxies `/api/*` to `127.0.0.1:4001`, so there is no CORS to
worry about.

> **v0.4b note** — for now the dev workflow keeps backend and
> frontend as separate processes. The Tauri shell in v0.4c will boot
> the backend automatically so the user only ever sees the desktop
> app.

## Stack

* React 18 + TypeScript 5 (strict)
* Vite 5
* Tailwind CSS v4 (plugin Vite, no PostCSS config needed)
* TanStack Query for API state
* `react-router-dom` for routing
* Lucide for icons
* Native `EventSource` behind a `useJobEvents` hook

## Scripts

| `npm run …`   | Cosa fa                                    |
|---------------|--------------------------------------------|
| `dev`         | Vite dev server con HMR                    |
| `build`       | `tsc --noEmit` + `vite build`              |
| `preview`     | Anteprima della build di produzione        |
| `typecheck`   | Solo controllo TypeScript                  |

## Layout sorgenti

```
src/
  main.tsx             entry-point, monta QueryClient + Router
  app/                 routing + provider applicativi
    App.tsx
    routes.tsx
  components/          UI riusabile (AppShell, StatusPill, …)
  lib/                 api.ts (fetch typed), events.ts (SSE), format.ts
  pages/               una pagina per route
```
