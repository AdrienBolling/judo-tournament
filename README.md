# judo-tournament

A web app to help manage small judo tournaments: import inscription tables,
auto-generate balanced round-robin pools with a genetic-algorithm solver, score
matches live, and produce results reports.

## Architecture

- **Backend** — Python, [FastAPI](https://fastapi.tiangolo.com/) over a
  SQLModel/SQLite domain layer (`src/backend`). The HTTP/JSON API lives in
  `src/api`.
- **Frontend** — [SvelteKit](https://svelte.dev/docs/kit) (Svelte 5) single-page
  app in `frontend/`, talking to the API over `fetch`.
- A legacy [Streamlit](https://streamlit.io/) UI still exists under `src/app`
  (kept for reference; superseded by the SvelteKit frontend).

Roles: **admin** (clubs, coaches, tournaments, groups, tokens), **coach**
(their club's members + results), **referee** (live scoring via a per-table
token). Admin/coach authenticate with a password → JWT; referees exchange a
tournament token for a scoped JWT.

## Running it (development)

You need **two** processes: the API and the frontend dev server.

### 1. Backend (FastAPI) — port 8000

```bash
uv sync
# Optional but recommended for anything real:
export JUDO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uv run uvicorn api.main:app --reload --port 8000
```

Interactive API docs: <http://localhost:8000/docs>

### 2. Frontend (SvelteKit) — port 5173

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api/*` to
`http://localhost:8000`, so the browser only ever talks to one origin (no CORS
needed in dev).

On first launch the app detects there's no admin account and walks you through
creating one.

### Seed demo data (optional)

```bash
uv run python scripts/seed_db.py
```

Prints demo logins (admin / coach emails) and referee tokens.

## Configuration (environment variables)

| Variable             | Default                         | Purpose                                             |
| -------------------- | ------------------------------- | --------------------------------------------------- |
| `JUDO_SECRET_KEY`    | dev placeholder (32+ chars)     | JWT signing key. **Set this in production.**        |
| `JUDO_DB_PATH`       | `./judo_tournament.db`          | SQLite database file path.                          |
| `JUDO_CORS_ORIGINS`  | `http://localhost:5173,…`       | Comma-separated allowed origins (for the API CORS). |

## Production build

```bash
cd frontend && npm run build      # static SPA in frontend/build/
```

Serve `frontend/build/` from any static host (or behind the same reverse proxy
as the API) and run the API with a production ASGI server, e.g.:

```bash
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Point the proxy's `/api` at the API and serve the SPA's `index.html` as the
fallback for all other routes.

## Tests

```bash
uv run pytest            # backend / domain tests
cd frontend && npm run check   # frontend type-check
```
