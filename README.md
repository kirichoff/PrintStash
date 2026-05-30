<p align="center">
  <img src="screenshots/00-demo.gif" alt="PrintStash demo" width="720" />
</p>

<h1 align="center">PrintStash</h1>

<p align="center">
  <strong>Self-hosted asset management for 3D printing.</strong><br/>
  Drop in STLs, 3MFs, and G-code. Search, tag, slice, reprint.<br/>
  Months later — no guessing which settings made that perfect benchy.
</p>

<p align="center">
  <a href="./LICENSE"><img alt="AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-blue?style=flat-square" /></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&style=flat-square" />
  <img alt="Next.js" src="https://img.shields.io/badge/next.js-14-black?logo=next.js&style=flat-square" />
  <img alt="Docker" src="https://img.shields.io/badge/docker-ready-2496ED?logo=docker&style=flat-square" />
  <img alt="Stage 4" src="https://img.shields.io/badge/stage-4%20%7C%20production%20hardening-brightgreen?style=flat-square" />
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#features">Features</a> ·
  <a href="#api">API</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#development">Development</a> ·
  <a href="#roadmap">Roadmap</a>
</p>

---

## Quick start

**You need:** Docker & Docker Compose. That's it.

```bash
git clone https://github.com/anomalyco/nexus3d-vault.git
cd nexus3d-vault

cp .env.example .env
# ⚠️ Edit .env — change VAULT_API_KEY and VAULT_JWT_SECRET to something random

docker compose up -d
```

| Service   | URL                                    |
| --------- | -------------------------------------- |
| Web UI    | [http://localhost:3000](http://localhost:3000) |
| API docs  | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Health    | `http://localhost:8000/api/v1/health`  |

> **First launch** — open `http://localhost:3000`. The setup wizard lets you
> create an admin account and pick where files live. There is no default login.

---

## Features

### 🔍 Auto-extraction & deduplication
Drop in a file and PrintStash pulls out everything it can find:
- **G-code** — slicer name & version, printer model, nozzle diameter, layer height,
  infill %, estimated print time, filament weight/length/cost, material type & brand,
  embedded thumbnail
- **STL / 3MF** — bounding box dimensions, volume, triangle count
- **Everything** — SHA‑256 content hash for deduplication. Re‑upload the same file
  and it's a no‑op. No duplicates, ever.

### 📦 Version tracking
Slice the same model again with different settings? Both G‑code versions live under
one model entry. Switch between profiles without losing history.

### 🗂️ Organization
- **Hierarchical categories** — `Functional/Brackets`, `Decorative/Planters`,
  `Printer Upgrades/Fans` — with a tree browser in the UI
- **Flat tags** — `PLA`, `PETG`, `workshop`, `gift` — fast, orthogonal filtering
- **Full-text search** across names, tags, categories, and descriptions

### 🎨 Web UI
- Next.js 14 App Router with server components for fast page loads
- Shadcn/ui components, Tailwind CSS, full responsive layout (sidebar on desktop,
  bottom nav + drawer on mobile)
- **In‑browser 3D viewer** for STL files (React Three Fiber) — rotate, zoom, inspect
- Light/dark mode
- First-run setup wizard — no default accounts, no hardcoded passwords

### 🖨️ Multi-provider printer integration (Stage 4f)
- **Register printers** with provider-aware config (`moonraker` or `bambu_lan`) — one printer or a whole farm
- **Send to print** from the vault — pick a G‑code file, pick a printer, hit send.
  Optionally start the print immediately (Moonraker path).
- **Live status** — per‑printer WebSocket streams temperatures, progress, printer
  state, toolhead position. Reconnects automatically.
- **Print controls** — pause, resume, cancel from the UI
- **Print history** — every job tracked with timestamps, progress, and errors.
  Jobs started outside the vault (directly on Klipper) are automatically captured.
- **Farm dashboard** — at‑a‑glance: ready / printing / offline counts, per‑group
  breakdown. `GET /api/v1/printers/dashboard`
- **Printer groups** — tag printers by location (`garage`, `workshop`, `enclosure`).
  Filter in the UI with `?group=garage`.
- **Capability-aware controls** — per-printer capabilities are exposed by API so
  the UI can disable unsupported operations safely.
- **Bambu LAN support (first milestone)** — LAN-first status + pause/resume/cancel.
  File upload/send parity is intentionally deferred.

### ⚡ OrcaSlicer hook
Drop `scripts/nexus3d_orca_push.py` into your OrcaSlicer post-processing scripts
folder. Zero dependencies — stdlib only (`urllib` + `hashlib`). Every slice
auto‑uploads to your vault.

```bash
# OrcaSlicer → Print Settings → Advanced → Post-processing Scripts:
/usr/bin/python3 /path/to/nexus3d_orca_push.py \
    --url http://your-printstash:8000 \
    --api-key YOUR_API_KEY \
    --category "Functional/Brackets"
```

The hook **never blocks your slice** — if the vault is down, it logs the failure
and exits 0 so OrcaSlicer continues without interruption.

### 📸 Screenshots

<p align="center">
  <img src="screenshots/01-asset-grid.png" alt="Asset grid" width="280" />
  <img src="screenshots/02-category-filter.png" alt="Categories" width="280" />
  <img src="screenshots/04-model-detail.png" alt="Model detail" width="280" />
  <img src="screenshots/05-3d-viewer.png" alt="3D viewer" width="280" />
  <img src="screenshots/06-setup-wizard.png" alt="Setup wizard" width="280" />
</p>

---

## API

Every feature the web UI has is available through the REST API. Auth via
`X-API-Key` header (scripts/hooks) or JWT Bearer token (logged‑in users).
Full OpenAPI (Swagger) interactive docs at `/docs`.

### Models & files

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `POST` | `/api/v1/ingest/orca` | key | Multipart upload (OrcaSlicer‑compatible) |
| `GET` | `/api/v1/models` | — | List / search (`?q=`, `?category=`, `?tag=`) |
| `GET` | `/api/v1/models/{id}` | — | Single model with all files & metadata |
| `PATCH` | `/api/v1/models/{id}` | key | Update name, description, categories, tags |
| `DELETE` | `/api/v1/models/{id}` | key | Soft‑delete (file kept on disk) |
| `GET` | `/api/v1/files/{id}/raw` | — | Download file (streamed, supports Range) |
| `GET` | `/api/v1/files/{id}/stl` | — | Serve raw STL for the 3D viewer |
| `GET` | `/api/v1/files/{id}/thumbnail` | — | Pre‑rendered PNG thumbnail |

### Taxonomy

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `GET` / `POST` | `/api/v1/taxonomy/categories` | —/key | List or create category |
| `PATCH` / `DELETE` | `/api/v1/taxonomy/categories/{id}` | key | Rename or remove category |
| `GET` / `POST` | `/api/v1/taxonomy/tags` | —/key | List or create tag |
| `DELETE` | `/api/v1/taxonomy/tags/{id}` | key | Remove tag |
| `PUT` | `/api/v1/taxonomy/models/{id}/tags` | key | Replace all tags on a model |

### Printers & farm (Stage 4f provider-aware)

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `GET` | `/api/v1/printers` | — | List printers (`?group=garage` filter) |
| `GET` | `/api/v1/printers/dashboard` | — | Farm health summary (counts per status, groups) |
| `POST` | `/api/v1/printers` | key | Register a new printer (`provider` + provider credentials) |
| `PATCH` | `/api/v1/printers/{id}` | key | Update name, provider config, credentials, group, notes |
| `DELETE` | `/api/v1/printers/{id}` | key | Remove a printer |
| `POST` | `/api/v1/printers/{id}/send` | key | Upload vault G‑code to printer; optionally start print |
| `POST` | `/api/v1/printers/{id}/pause` | key | Pause the active print job |
| `POST` | `/api/v1/printers/{id}/resume` | key | Resume a paused print |
| `POST` | `/api/v1/printers/{id}/cancel` | key | Cancel the active print |
| `GET` | `/api/v1/printers/{id}/status` | — | One‑shot status snapshot + cached provider state |
| `GET` | `/api/v1/printers/{id}/jobs` | — | Print job history (recent 50 by default) |
| `WS` | `/api/v1/printers/{id}/ws` | — | Live WebSocket status stream |

### System

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `POST` | `/api/v1/setup` | — | Initialize admin user (one‑time, wizard) |
| `GET` | `/api/v1/setup/status` | — | Is setup completed? |
| `POST` | `/api/v1/auth/token` | — | Login → JWT access token |
| `POST` | `/api/v1/config` | key | Update runtime settings (storage paths, S3, backup) |
| `GET` | `/api/v1/config` | — | Read current configuration |
| `POST` | `/api/v1/backup` | key | Create & download a backup archive |
| `GET` | `/api/v1/backup` | key | List available backup archives |

> **Note:** All write endpoints accept **either** `X-API-Key` **or** JWT.
> Read endpoints are open by default. Lock down writes behind your API key.

### Quick API test

```bash
# Ingest a G-code file (OrcaSlicer-compatible endpoint)
curl -F "file=@my_print.gcode" \
     -F "model_name=Desk Bracket" \
     -F "category=Functional/Brackets" \
     -H "X-API-Key: YOUR_KEY_HERE" \
     http://localhost:8000/api/v1/ingest/orca

# List your models
curl http://localhost:8000/api/v1/models

# Check farm health
curl http://localhost:8000/api/v1/printers/dashboard
```

---

## Configuration

All settings come from environment variables prefixed with `VAULT_`.
See `.env.example` for the full annotated list.

| Variable | Default | Description |
|----------|---------|-------------|
| `VAULT_API_KEY` | `changeme` | Shared key for OrcaSlicer hooks and headless scripts |
| `VAULT_JWT_SECRET` | `changeme_jwt_…` | Secret for signing user login tokens |
| `VAULT_JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `VAULT_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Session timeout |
| `VAULT_STORAGE_BACKEND` | `local` | `local` (files on disk) or `s3` (object storage) |
| `VAULT_DATA_DIR` | `/data/files` | Canonical file storage root (container‑absolute) |
| `VAULT_THUMB_DIR` | `/data/thumbs` | Rendered PNG thumbnails |
| `VAULT_STAGING_DIR` | `/data/staging` | In‑flight upload buffer (always local) |
| `VAULT_DB_URL` | `sqlite:////data/db/nexus3d.sqlite` | SQLite path (Postgres in Stage 4) |
| `VAULT_BACKUP_DIR` | `/data/backups` | Directory for tar.gz backup archives |
| `VAULT_BACKUP_RETENTION_DAYS` | `30` | Auto‑purge backups older than N days |
| `VAULT_BACKUP_S3_*` | — | Optional S3/R2 bucket for off‑site backups |
| `VAULT_S3_*` | — | S3 credentials (when `VAULT_STORAGE_BACKEND=s3`) |
| `VAULT_MAX_UPLOAD_MB` | `512` | Maximum upload size in MB |
| `VAULT_LOG_LEVEL` | `INFO` | Python logging level |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000` | Browser‑side WebSocket URL for live printer status |

Printer provider fields:
- `provider`: `moonraker` or `bambu_lan`
- Moonraker: `moonraker_url`, optional `api_key`
- Bambu LAN: `bambu_host`, `bambu_serial`, `bambu_access_code`

### File storage layout (inside the container)

```
/data/
├── files/                          ← canonical file storage
│   ├── _incoming/<uuid>.<ext>      ← staging for in‑flight uploads
│   └── <model_slug>/v<version>/    ← permanent home after ingest
├── thumbs/<file_id>.png            ← extracted / rendered previews
├── staging/                        ← temp space for upload processing
├── db/nexus3d.sqlite               ← single SQLite database
└── backups/                        ← tar.gz backup archives
```

> **Host access:** All paths are container‑absolute. Map host folders via Docker
> named volumes (`vault_data`, `vault_thumbs`, `vault_db`, `vault_staging`,
> `vault_backups`). Data survives `docker compose down`.

---

## Architecture

```
 ┌──────────────────────────────────────────────────────────────┐
 │  Clients                                                     │
 │  ┌──────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
 │  │ Browser  │  │ OrcaSlicer  │  │ Scripts / Z‑Suite / etc │  │
 │  └────┬─────┘  └──────┬──────┘  └────────────┬────────────┘  │
 └───────┼───────────────┼──────────────────────┼───────────────┘
         │ HTTP + WS     │ HTTP (multipart)     │ HTTP
         ▼               ▼                      ▼
 ┌───────────────────────────────────────────────────────────────┐
 │  PrintStash                                                   │
 │                                                               │
 │  ┌──────────────────────┐    ┌──────────────────────────────┐ │
 │  │  Frontend (Next.js)  │    │  API (FastAPI, port 8000)    │ │
 │  │  port 3000           │    │                              │ │
 │  │                      │    │  ◇ /api/v1/models            │ │
 │  │  ◇ Server components │    │  ◇ /api/v1/printers          │ │
 │  │  ◇ R3F 3D viewer     │◄──►│  ◇ /api/v1/taxonomy          │ │
 │  │  ◇ Shadcn/ui         │    │  ◇ /api/v1/ingest            │ │
 │  │  ◇ WebSocket client  │    │  ◇ WebSocket (live status)   │ │
 │  └──────────────────────┘    └──────────────┬───────────────┘ │
 │                                             │                  │
 │                        ┌────────────────────┼───────────────┐ │
 │                        │  Services          │               │ │
 │                        │                    ▼               │ │
 │                        │  ◇ PrinterHub ◇ Provider adapters   │ │
 │                        │  ◇ G‑code parser ◇ Ingest pipeline │ │
 │                        │  ◇ Mesh processing ◇ Thumbnails    │ │
 │                        │  ◇ Storage backend (local / S3)    │ │
 │                        └────────────────────┬───────────────┘ │
 │                                             │                  │
 │                        ┌────────────────────┼───────────────┐ │
 │                        │  Data              ▼               │ │
 │                        │  ┌──────────────────────────────┐  │ │
 │                        │  │  SQLite (/data/db/)          │  │ │
 │                        │  └──────────────────────────────┘  │ │
 │                        │  ┌──────────────────────────────┐  │ │
 │                        │  │  Named volumes (files/thumbs)│  │ │
 │                        │  └──────────────────────────────┘  │ │
 │                        └────────────────────────────────────┘ │
 └───────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
 ┌──────────────────┐    ┌──────────────────────────────┐
 │  Moonraker /     │    │  S3 / R2 (optional)          │
 │  Bambu LAN       │    │  Cloud storage & backups     │
 │  (your printers) │    │                              │
 └──────────────────┘    └──────────────────────────────┘
```

### Tech stack

| Layer | Technology |
|-------|-----------|
| **API** | FastAPI, Pydantic v2, SQLModel (SQLAlchemy 2), Uvicorn |
| **Database** | SQLite (Stages 1–3) → PostgreSQL (Stage 4) |
| **3D processing** | Trimesh, NumPy, Pillow (lazy imported) |
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, Shadcn/ui, React Three Fiber |
| **Infra** | Docker Compose, named volumes, health checks |
| **Optional Rust** | `_nexus3d_rust` wheel for faster G‑code scanning & thumbnail rendering |
| **Integration** | OrcaSlicer post‑processing hook (stdlib only), Moonraker API, Bambu LAN controls |
| **Testing** | pytest, pytest‑asyncio, in‑memory SQLite, FastAPI TestClient |

### Key design decisions

- **API‑first** — the web UI is a consumer of the same API scripts and other tools use
- **Soft deletes** — `DELETE` endpoints set a `deleted_at` flag; files are never
  hard‑deleted in Stage 1–3
- **Background work** — FastAPI `BackgroundTasks` for ingestion; no Celery/Redis
  until Stage 3
- **Printer hub** — singleton `PrinterHub` on `app.state` maintains one persistent
  live-state worker per printer via provider adapters, with exponential backoff reconnection
- **ORM choice** — SQLModel today specifically so the Postgres jump in Stage 4
  is a config change, not a rewrite

---

## Development

### Prerequisites
- Python 3.11+ with [`uv`](https://docs.astral.sh/uv/)
- Node.js 20+ with [`pnpm`](https://pnpm.io/)

### Local backend

```bash
cd backend
uv sync --extra dev

# Run with ephemeral SQLite (data lost on restart — good for dev)
VAULT_API_KEY=devkey \
  VAULT_DB_URL=sqlite:///./dev.sqlite \
  VAULT_DATA_DIR=./_data/files \
  VAULT_THUMB_DIR=./_data/thumbs \
  uv run uvicorn app.main:app --reload
```

### Local frontend

```bash
cd frontend
pnpm install
pnpm dev
# → http://localhost:3000
# Points to the API at localhost:8000 by default
```

### Tests

```bash
cd backend
uv run pytest tests -v          # all tests
uv run pytest tests/test_printer_hub.py -v   # just one file
```

118 tests across: Moonraker HTTP+WS client, provider adapters, PrinterHub worker, Printers API router,
Rust acceleration wrappers, and the G‑code ingestion pipeline.

### Lint & format

```bash
cd backend
uv run ruff check app/ tests/   # lint
uv run ruff format app/ tests/  # format
```

```bash
cd frontend
pnpm lint
```

### Project layout

```
3dnexus/
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── rust/                    ← optional Rust native extension
│   ├── app/
│   │   ├── main.py              ← FastAPI app factory + lifespan
│   │   ├── core/                ← config, security, logging, time, http helpers
│   │   ├── db/                  ← SQLModel models, session factory, init + migrations
│   │   ├── schemas/             ← Pydantic request/response DTOs
│   │   ├── services/            ← business logic (ingest, gcode parser, providers, etc.)
│   │   └── api/v1/              ← versioned routers (models, printers, taxonomy, etc.)
│   └── tests/                   ← pytest (118 tests, in‑memory SQLite)
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   └── src/
│       ├── app/                 ← Next.js 14 App Router pages
│       ├── components/          ← UI components (Shadcn + custom)
│       ├── lib/                 ← API client, auth, errors, utils
│       └── types/               ← Shared TypeScript types
├── scripts/
│   └── nexus3d_orca_push.py     ← OrcaSlicer post‑processing hook
├── docs/
│   └── stage1.md                ← Stage 1 execution log
├── screenshots/                 ← Demo screenshots
├── .env.example                 ← All config options with comments
└── docker-compose.yml
```

---

## Roadmap

Detailed roadmap: [docs/roadmap.md](./docs/roadmap.md)

| Stage | Status | What's included |
|:-----:|:------:|-----------------|
| **1** — Headless Vault | ✅ | Ingestion, metadata extraction, dedup, thumbnails, REST API, SQLite |
| **2** — Visual Experience | ✅ | Next.js UI, 3D viewer, setup wizard, auth, categories, tags, search |
| **3** — The Hub | ✅ | Moonraker/Klipper integration, printer farm, live status WS, print history, OrcaSlicer hook, dashboard |
| **4** — Production Hardening | ✅ | Alembic migrations, Postgres/S3 optional adapters, auth hardening, lifecycle/audit controls, provider architecture + Bambu LAN milestone |

---

## What PrintStash is NOT

- **Not a slicer** — bring your own sliced G‑code. PrintStash catalogs what you
  already produce.
- **Not a cloud service** — runs entirely on your hardware. Cloud features (S3,
  Postgres, multi‑tenant) are Stage 4 and will always be opt‑in.
- **Not a print queue manager** — Moonraker/Bambu firmware owns the print queue.
  PrintStash sends jobs to your printers and tracks their state, but the queue
  disciplines live on the printer firmware.

---

## Contributing

Bug reports and PRs are welcome. Please:

1. Open an issue to discuss what you're changing before opening a PR
2. Follow the conventions in [AGENTS.md](./AGENTS.md) (PEP 8, 4‑space indent,
   type hints on public functions, no bare `except:`, lazy import `trimesh`)
3. Add tests — `backend/tests/` uses `pytest` with in‑memory SQLite
4. Run `ruff check` and `ruff format` before pushing

---

## License

[GNU AGPL-3.0](./LICENSE) — if you improve it, share back. If you're just running
it on your own server for your own prints, the license doesn't get in your way.
