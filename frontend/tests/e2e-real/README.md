# Real end-to-end tests

These Playwright specs drive the **real** FastAPI backend against a throwaway
SQLite DB + temp data dirs — every create/edit/delete actually hits the database.
This is the difference from `tests/e2e/` (the fast mock-API smoke suite).

```bash
pnpm test:e2e:real
```

`playwright.real.config.ts` boots two web servers:

- `scripts/start-backend.sh` — wipes state, runs Alembic, launches uvicorn on
  `:8410` against a temp DB under `.data/` (gitignored).
- Vite on `:3310` with `VITE_API_URL` pointed at that backend.

`helpers.ts` seeds the first admin via `/setup` once and injects a real JWT into
the browser, so tests boot authenticated. The suite runs serially on one DB, so
tests use unique (timestamped) names and clean up after themselves.

Requires the backend dev venv (`backend/.venv`); falls back to `uv run`.

## Coverage

auth (UI login, wrong-password, username + API-key login then revoke) ·
collections (create / nest / delete) · tags · filament & printer presets
(create / edit / delete) · model lifecycle (upload → edit → trash → restore →
purge) · G-code revisions (add, auto-recommend, re-recommend, status, compare) ·
public share links (view-only vs downloadable, revoke → 404) · RBAC (create
user, grant collection access, non-admin sees only granted collections) · user
management (promote/disable/reset password) · API keys · display currency ·
metadata export · manual backup · design customization (metadata visibility) ·
printer add/remove · cross-cutting (theme persistence, health version, routes
free of uncaught errors).

`util.ts` uploads a model through the real ingest flow; its G-code embeds the
model name so the backend's content-hash dedupe doesn't collapse separate
uploads. `helpers.ts` also exposes `authBundleFor`/`authedContext` to drive a
second browser as a non-admin user.
