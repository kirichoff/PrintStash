---
title: Development
description: Backend and frontend setup, checks, and tests for contributors.
---

Bug reports, hardware notes, parser fixtures, docs fixes, and small PRs are
welcome. Start with `CONTRIBUTING.md` in the repository.

## Prerequisites

- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) for the backend
- Node.js and [`pnpm`](https://pnpm.io/) for the frontend
- Docker and Docker Compose for the full stack

:::note
The backend uses `uv` (not `pip`) and the frontend uses `pnpm` (not `npm`).
:::

## Backend

```bash
cd backend
uv sync                  # install dependencies
uv run uvicorn app.main:app --reload   # run the dev server

# Checks
uv run ruff check .      # lint
uv run ruff format .     # format
uv run pytest            # tests
```

The backend keeps a one-directional dependency: routers (`api/`) call services
(`services/`), and **services never import from `api/` or `fastapi`**. Use
`get_config()` for settings rather than importing the settings object directly.
See [Architecture](/PrintStash/reference/architecture/).

## Frontend

```bash
cd frontend
pnpm install
pnpm dev                 # Vite dev server

# Checks
pnpm lint                # eslint
pnpm typecheck           # tsc --noEmit
pnpm test                # Vitest unit tests
pnpm test:coverage       # Vitest with a coverage report
pnpm test:e2e            # Playwright end-to-end
```

Unit tests live next to the code in `src/**/__tests__/` and run in jsdom via
Vitest; the Playwright suite under `tests/e2e/` drives the built app against a
mock API. Run `pnpm test` after changes to `lib/` logic.

Use the typed API layer in `lib/api/<domain>.ts` (never raw `fetch`) and the
TanStack Query hooks in `lib/queries.ts` for cached reads. Run lint and
typecheck after changes.

## Mock printer (testing without hardware)

`backend/tests/e2e/fakes/mock_printer.py` is a standalone service that speaks the
Moonraker HTTP + WebSocket surface **and** hosts a minimal Spoolman, with a
simulated print lifecycle. Use it to exercise the send → print → file tracking →
filament usage → Spoolman write-back flow without a physical printer.

Run it locally alongside the backend:

```bash
cd backend
uv run python -m tests.e2e.fakes.mock_printer --port 7125 --print-seconds 30
```

Flags: `--total-mm` (filament length), `--total-seconds` (reported estimate),
`--print-seconds` (real time to complete — keep it short for testing),
`--api-key` (optional). Then in the app, add a printer with:

- **Moonraker URL:** `http://localhost:7125`
- **Spoolman base URL** (Settings → Spoolman): `http://localhost:7125/spoolman`

Start a print and the simulated job progresses to completion, after which the
mock Spoolman spool's remaining weight is decremented.

For the dockerized stack, the mock is wired into `docker-compose.build.yml`
behind the `mock` profile (register the printer at `http://mock-printer:7125`):

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml \
  --profile mock up mock-printer
```

The end-to-end pipeline is covered by
`backend/tests/test_mock_printer_integration.py` (`uv run pytest
tests/test_mock_printer_integration.py`).

## Documentation (this site)

The wiki is an [Astro Starlight](https://starlight.astro.build/) site under
`docs/wiki/`.

```bash
cd docs/wiki
pnpm install
pnpm dev                 # local preview at http://localhost:4321
pnpm build               # production build into dist/
```

Pages are Markdown/MDX under `src/content/docs/`. The sidebar is configured in
`astro.config.mjs`. Each page has an **Edit** link pointing back at its source
file on GitHub.
