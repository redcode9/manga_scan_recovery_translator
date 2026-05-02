# msrt-desktop

Local web UI for `msrt`. In produzione `uv run msrt ui` serve sia API
FastAPI sia bundle React su `http://127.0.0.1:4001`.

## Quick start (single command)

```bash
uv run msrt ui
```

Il comando builda `apps/desktop` se serve, avvia il backend e apre il
browser sulla UI. Per sviluppo frontend usa il flusso a due processi qui sotto.

## Quick start (development)

```bash
# 1) Backend API + static serving disabled for HMR
uv run msrt ui --no-build --no-open

# 2) Frontend (in another terminal)
cd apps/desktop
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). The Vite dev
server proxies `/api/*` to `127.0.0.1:4001`, so there is no CORS to
worry about.

> **Dev note** — HMR usa due processi. L'uso normale resta un solo
> comando (`uv run msrt ui`).

## Stack

* React 18 + TypeScript 5 (strict)
* Vite 5
* Tailwind CSS v4 (plugin Vite, no PostCSS config needed)
* TanStack Query for API state
* `react-router-dom` for routing
* Lucide for icons
* Native `EventSource` behind a `useJobEvents` hook
* Tauri 2 scaffold in `src-tauri/` for future desktop packaging

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
