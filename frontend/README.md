# Frontend

React + TypeScript + Vite + Tailwind CSS + React Router + TanStack Query. See
`docs/adr/03_FRONTEND.md` for the stack decision and screen scope.

## Development

Requires the backend API (`app/main.py`, the Postgres-backed `app/api/v1` routes) running with
Postgres and Redis migrated (`alembic upgrade head`) — see `docker-compose.yaml`'s `api` service,
or run `uvicorn app.main:app --port 8001` locally.

```bash
cp .env.example .env.development.local  # set VITE_API_BASE_URL if the API isn't on :8001
npm install
npm run dev
```

The backend's `cors_origins` (`app/config.py`) already allows `http://localhost:5173`.

## Scripts

- `npm run dev` — Vite dev server
- `npm run build` — typecheck (`tsc -b`) + production build
- `npm run lint` — oxlint

## Structure

- `src/lib/api.ts` — typed fetch client (cookie session + CSRF header)
- `src/auth/` — current-user query hook
- `src/pages/` — routed screens
- `src/components/` — shared layout/UI pieces
