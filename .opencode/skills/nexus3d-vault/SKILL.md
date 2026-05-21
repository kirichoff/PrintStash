---
name: nexus3d-vault
description: Architecture, data model, ingestion pipeline, UI components, and operational workflows for the Nexus3D Vault — a self-hosted, Plex-style 3D printing asset manager (FastAPI + SQLModel + SQLite + Docker + Next.js 14 + R3F). Load this skill when working on backend services, API endpoints, frontend pages, 3D viewer components, OrcaSlicer integration, the data schema, or planning future stages.
---

# Skill: Nexus3D Vault

This skill captures the **canonical architecture** of Nexus3D Vault. It is the
source of truth for shape, contracts, and pipelines. Update it whenever an
architectural decision changes.

---

## 1. Mission & Stages

Nexus3D Vault is the "Plex for 3D printing": a self-hosted, API-first vault that
ingests STL/3MF/G-Code assets, deduplicates them, extracts metadata, and serves
them via REST.

| Stage | Codename              | Status   | Adds                                                                  |
| ----- | --------------------- | -------- | --------------------------------------------------------------------- |
| 1     | The Headless Vault    | completed | FastAPI core, SQLite/SQLModel, Docker, OrcaSlicer ingestion, parser  |
| 2     | The Visual Experience | completed | Next.js 14 + Shadcn UI, asset grid, R3F viewer, manual uploads        |
| 3     | The Hub               | active   | Moonraker/Klipper bridge: send-to-print, live state, print history    |
| 4     | Cloud Readiness       | planned  | OAuth2/JWT, multi-tenant, Postgres + Alembic, S3 adapter, audit logs  |

---

## 1b. Stage 3 surface (current)

- **DB:** `printer`, `print_job`, `category`, `tag`, `model_tag_link` tables plus
  `Model.category_id` / `Model.thumbnail_file_id`. SQLite migrations are still
  hand-rolled in `db/session.py::_apply_column_patches()` (Alembic comes in Stage 4).
- **Services:** `services/moonraker.py` (HTTP + WS client) and
  `services/printer_hub.py` (`hub` singleton — one subscription per printer, snapshot
  cache, browser WS fan-out, `PrintJob` state reconciliation).
- **API:**
  - `GET /api/v1/categories`, `GET /api/v1/tags` (read-only facets with counts)
  - `GET /api/v1/models?category=…&tag=…&tag=…` — prefix category match + tag-AND
  - `PATCH /api/v1/models/{id}` — edit name/description/category/tags
  - `GET/POST/PATCH/DELETE /api/v1/printers[/{id}]`
  - `POST /api/v1/printers/{id}/send` — upload + optional `start_print`; returns `PrintJob`
  - `POST /api/v1/printers/{id}/{pause|resume|cancel}`
  - `GET /api/v1/printers/{id}/status` — cached snapshot
  - `GET /api/v1/printers/{id}/jobs` — recent history
  - `WS /api/v1/printers/{id}/ws` — `{type: "snapshot"|"update", printer_id, data}`
- **Frontend:** `/printers` index + `/printers/[id]` live page (reconnecting WS),
  `FilterSidebar` on `/` for category tree + tag chips, `SendToPrinterButton` on
  model detail. Browser WS URL comes from `NEXT_PUBLIC_WS_URL` because Next.js
  rewrites do not proxy WebSockets.
- **Thumbnails:** pure-CPU numpy+Pillow renderer in `services/mesh_processing.py`
  (no Trimesh/matplotlib in the render path); STL/3MF uploads always produce a preview.

---

## 2. Stage 1 Architecture (Current)

```
┌──────────────┐ multipart/form-data  ┌──────────────────────────────┐
│ OrcaSlicer   │ ───────────────────► │ FastAPI (uvicorn :8000)      │
│ post-proc    │ X-API-Key            │  ┌────────────────────────┐  │
└──────────────┘                      │  │ /api/v1/ingest/orca    │  │
                                      │  │   → BackgroundTasks    │  │
┌──────────────┐ multipart            │  │      ├ checksum        │  │
│ Manual curl  │ ───────────────────► │  │      ├ gcode parse     │  │
└──────────────┘                      │  │      ├ thumbnail X     │  │
                                      │  │      ├ dedup           │  │
                                      │  │      └ persist         │  │
                                      │  └─────────┬──────────────┘  │
                                      └────────────┼─────────────────┘
                                                   ▼
                            ┌────────────────┬─────────────┬────────────────┐
                            │ vault_data     │ vault_db    │ vault_thumbs   │
                            │ blobs          │ sqlite file │ PNG previews   │
                            └────────────────┴─────────────┴────────────────┘
```

### Module map

```
backend/app/
├── main.py                  # app factory, lifespan (db init, dirs)
├── core/
│   ├── config.py            # pydantic-settings, env-driven
│   ├── logging.py           # get_logger() — stdlib logging
│   └── security.py          # X-API-Key dependency
├── db/
│   ├── session.py           # engine + get_session()
│   ├── init.py              # SQLModel.metadata.create_all
│   └── models.py            # Model, File, Metadata, FileType enum
├── schemas/
│   ├── ingest.py            # IngestResponse, IngestJobStatus
│   └── models.py            # ModelRead, FileRead, MetadataRead
├── services/
│   ├── storage.py           # path layout helpers, slugging, moves
│   ├── hashing.py           # sha256 streaming over UploadFile / Path
│   ├── gcode_parser.py      # OrcaSlicer header/footer parsing
│   ├── thumbnail.py         # base64 PNG extraction from gcode
│   └── ingestion.py         # the BackgroundTask orchestrator
└── api/v1/
    ├── __init__.py          # api_router, includes the below
    ├── health.py            # GET /health
    ├── ingest.py            # POST /ingest/orca, /ingest/model
    ├── models.py            # GET /models, GET /models/{id}, DELETE
    └── files.py             # GET /files/{id}/download | /thumbnail
```

---

## 2b. Stage 2 Architecture (Frontend)

```
┌──────────────────┐  HTTP / rewrite  ┌─────────────────────────────┐
│ Browser / User   │ ───────────────► │ Next.js 14 (port 3000)      │
│                  │                  │  ┌────────────────────────┐ │
│                  │                  │  │ /          (SSR grid)  │ │
│                  │                  │  │ /models/[id] (SSR detail│ │
│                  │                  │  │ /upload    (CSR form)  │ │
│                  │                  │  │ /api/v1/*  (rewrite)   │ │
│                  │                  │  └─────────┬──────────────┘ │
│                  │                  └────────────┼────────────────┘
│                  │                               │
│                  │          fetch / CORS         │
│                  │ ◄─────────────────────────────┘
│                  │                               ▼
│                  │                  ┌─────────────────────────────┐
│                  │                  │ FastAPI (port 8000)         │
│                  │                  │  ┌───────────────────────┐  │
│                  │                  │  │ /api/v1/models, files │  │
│                  │                  │  │ /api/v1/ingest/orca   │  │
│                  │                  │  └─────────┬─────────────┘  │
│                  │                  └────────────┼────────────────┘
│                  │                               │
│                  │                  ┌────────────┼────────────┐
│                  │                  ▼            ▼            ▼
│                  │           vault_data    vault_db    vault_thumbs
│                  │
│                  │  WebSocket (Stage 3)
│                  │ ◄──────────────────────────────────────────
│                  │              Moonraker / Klipper
```

### Frontend module map

```
frontend/src/
├── app/
│   ├── layout.tsx           # Root layout + Inter font + Header
│   ├── page.tsx             # Asset grid (Server Component)
│   ├── upload/page.tsx      # Manual upload (Client Component wrapper)
│   └── models/[id]/page.tsx # Model detail (Server Component)
├── components/
│   ├── ui/                  # Shadcn/ui primitives (button, card, input, badge, skeleton, separator)
│   ├── header.tsx           # Sticky nav bar
│   ├── model-card.tsx       # Thumbnail card for grid
│   ├── model-grid.tsx       # Responsive grid + search filter
│   ├── model-detail.tsx     # Two-column detail (thumbnail, R3F viewer, metadata, files)
│   ├── stl-viewer.tsx       # R3F Canvas + STLLoader + OrbitControls
│   └── upload-form.tsx      # Drag-drop zone, form, API key, progress
├── lib/
│   ├── utils.ts             # cn() — clsx + tailwind-merge
│   └── api.ts               # Typed fetch wrappers (listModels, getModel, ingestOrca, deleteModel)
└── types/
    └── index.ts             # TypeScript interfaces mirroring backend DTOs
```

### Key frontend decisions
- **Server Components by default** — `page.tsx` and `layout.tsx` are RSC; data fetching happens server-side for SEO and initial paint speed.
- **Client Components where needed** — `upload-form.tsx` and `stl-viewer.tsx` use `"use client"` for interactivity and R3F Canvas.
- **Next.js rewrites** — `/api/v1/:path*` is rewritten to the backend. In Docker, `NEXT_PUBLIC_API_URL=http://api:8000` is baked into the build so the rewrite resolves to the API container internally. `getAssetUrl()` in `lib/api.ts` returns relative URLs in the browser (through the rewrite) and absolute internal URLs during SSR.
- **CORS** — FastAPI `CORSMiddleware` is enabled (`allow_origins=["*"]`) as a fallback for direct browser-to-API access.
- **Images** — Standard `<img>` tags for API-served thumbnails (avoids Next.js Image optimization complexity with rewrite proxies). `<Image>` remains available for static assets.
- **R3F viewer** — Uses `three/examples/jsm/loaders/STLLoader` with auto-centering and scale normalization. Falls back to thumbnail if no STL is available.

---

## 3. Data Model

Three tables, kept normalized so Postgres migration in Stage 4 is mechanical.

- **Model** — logical asset, deduplicated by `hash` (source-mesh sha256, falls
  back to G-code blob sha256 when no source is available). Has `slug` for
  filesystem layout.
- **File** — physical artifact on disk. Many-to-one with Model. Carries
  `file_type` (stl/3mf/gcode/obj), `version` (per-model auto-increment),
  `sha256`, `size_bytes`, container-absolute `path`.
- **Metadata** — 1:1 with File. Slicer-derived (estimated_time_s,
  filament_weight_g, material_type, layer/nozzle/infill, printer_model,
  slicer_version) plus geometry (bbox/volume/triangle_count) when available.

### Key invariants
- `Model.slug` is unique, kebab-case, derived from `name` with collision suffix.
- `File.path` is **container-absolute** (`/data/files/<slug>/v<n>/<name>`).
- Soft delete only in Stage 1 (`Model.deleted_at` flag, query filter).
- Hashes lowercase 64-char hex, indexed.

---

## 4. Ingestion Pipeline (`services/ingestion.py`)

`POST /api/v1/ingest/orca` returns `202 Accepted` immediately and enqueues a
`BackgroundTask`. Pipeline:

1. **Stage upload** → `/data/files/_incoming/<uuid>.gcode` (streamed via
   `shutil.copyfileobj`, never `.read()`).
2. **Hash blob** → `File.sha256`.
3. **Parse G-code** → `services/gcode_parser.parse(path)` returns a dict of
   slicer fields (see §5).
4. **Extract thumbnails** → `services/thumbnail.extract(path)` returns the
   highest-resolution embedded PNG (bytes) or `None`.
5. **Determine dedup key** → prefer `source_hash` form field; otherwise use the
   G-code blob hash.
6. **Find or create Model** → if exists, `version = max(File.version) + 1`;
   else create with new slug.
7. **Move blob** → `/data/files/<slug>/v<version>/<original_filename>`.
8. **Write thumbnail** → `/data/thumbs/<file_id>.png`; set
   `Model.thumbnail_path` if not yet set.
9. **Insert Metadata** row.
10. **Job done** — status tracked in an in-memory dict keyed by `job_id`
    (Stage 1 only; Redis/Celery from Stage 3).

Failure handling: any step failure logs `ERROR` with stack trace and marks the
job `failed`. Staged file is left in `_incoming/` for forensic inspection
(GC in Stage 4).

---

## 5. G-Code Parser Contract

`parse(path: Path) -> dict` reads only the **first 64 KB and last 64 KB** of the
file (slicer metadata lives in headers/footers; saves I/O on huge prints).

Recognized OrcaSlicer comments (regex-driven):

| Field                  | Source comment                                         |
| ---------------------- | ------------------------------------------------------ |
| `slicer_version`       | `; generated by OrcaSlicer X.Y.Z`                      |
| `printer_model`        | `; printer_model = ...`                                |
| `nozzle_diameter_mm`   | `; nozzle_diameter = 0.4`                              |
| `layer_height_mm`      | `; layer_height = 0.2`                                 |
| `infill_percent`       | `; sparse_infill_density = 15%`                        |
| `estimated_time_s`     | `; estimated printing time (normal mode) = 1h 23m 45s` |
| `filament_weight_g`    | `; total filament used [g] = 24.83`                    |
| `filament_length_mm`   | `; total filament length [mm] = 8312.4`                |
| `filament_cost`        | `; total filament cost = 0.62`                         |
| `material_type`        | `; filament_type = PLA`                                |

Unknown / missing fields → `None`. Never raises on malformed input.

---

## 6. Thumbnail Extraction (`services/thumbnail.py`)

OrcaSlicer embeds previews as base64 between markers:

```
; THUMBNAIL_BLOCK_START
; thumbnail begin 512x512 12345
; iVBORw0KGgo...
; ...
; thumbnail end
; THUMBNAIL_BLOCK_END
```

Algorithm:
1. Stream the file once, collect blocks.
2. Pick the largest by `W*H`.
3. Strip `"; "` prefix per line, concat, `base64.b64decode`.
4. Return raw PNG bytes (caller writes to `/data/thumbs/<file_id>.png`).
5. If no block found, return `None`.

---

## 7. API Surface (Stage 1)

| Method | Path                              | Auth     | Purpose                          |
| ------ | --------------------------------- | -------- | -------------------------------- |
| GET    | `/api/v1/health`                  | none     | Liveness probe                   |
| POST   | `/api/v1/ingest/orca`             | API key  | Multipart G-code ingest          |
| POST   | `/api/v1/ingest/model`            | API key  | Multipart STL/3MF ingest         |
| GET    | `/api/v1/ingest/jobs/{job_id}`    | none     | Background task status           |
| GET    | `/api/v1/models`                  | none     | List w/ filters & pagination     |
| GET    | `/api/v1/models/{id}`             | none     | Detail + files + metadata        |
| DELETE | `/api/v1/models/{id}`             | API key  | Soft delete                      |
| GET    | `/api/v1/files/{id}/download`     | none     | Stream blob                      |
| GET    | `/api/v1/files/{id}/thumbnail`    | none     | Stream PNG (404 if absent)       |

Errors: `HTTPException(detail="<stable_string>")` — examples:
`model_not_found`, `file_not_found`, `unsupported_file_type`, `invalid_api_key`,
`ingest_failed`.

---

## 8. Configuration (env)

| Variable             | Default                          | Purpose                       |
| -------------------- | -------------------------------- | ----------------------------- |
| `VAULT_DB_URL`       | `sqlite:////data/db/nexus3d.sqlite` | SQLAlchemy URL              |
| `VAULT_DATA_DIR`     | `/data/files`                    | Blob root                     |
| `VAULT_THUMB_DIR`    | `/data/thumbs`                   | Thumbnail root                |
| `VAULT_API_KEY`      | *(required)*                     | Shared key for write endpoints|
| `VAULT_MAX_UPLOAD_MB`| `512`                            | Reject larger uploads (413)   |
| `VAULT_LOG_LEVEL`    | `INFO`                           | Logging level                 |

---

## 9. OrcaSlicer Integration

Script: `scripts/nexus3d_orca_push.py`. Configured in OrcaSlicer under
**Process → Others → Post-processing scripts**:

```
/usr/bin/python3 /path/to/nexus3d_orca_push.py \
    --url https://vault.example.com \
    --api-key $NEXUS3D_API_KEY \
    --category "Functional/Brackets"
```

Rules:
- **stdlib only** (no `requests`) — Orca users may not have a venv.
- **Always exit 0** — vault outage must never block slicing.
- Logs to `~/.nexus3d_orca_push.log`.
- Exponential backoff (3 attempts) on transient network errors; 4xx fail-fast.

---

## 10. Operational Runbook

### Local dev
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export VAULT_API_KEY=devkey
export VAULT_DB_URL=sqlite:///./dev.sqlite
export VAULT_DATA_DIR=./_data/files
export VAULT_THUMB_DIR=./_data/thumbs
uvicorn app.main:app --reload
# OpenAPI: http://localhost:8000/docs
```

### Docker
```bash
cp .env.example .env  # set VAULT_API_KEY
docker compose up --build -d
docker compose logs -f api
```

### Smoke test
```bash
curl -s http://localhost:8000/api/v1/health
curl -F "file=@sample.gcode" -F "model_name=Bracket v1" \
     -H "X-API-Key: devkey" \
     http://localhost:8000/api/v1/ingest/orca
```

### Backups
The three Docker volumes (`vault_data`, `vault_db`, `vault_thumbs`) are
self-contained. `docker run --rm -v vault_db:/d -v $PWD:/b alpine tar czf
/b/db.tgz -C /d .` is sufficient.

---

## 11. Decisions Log (Stage 1)

- **API key over JWT** — single shared `X-API-Key` header. Real auth deferred
  to Stage 4 to avoid carrying user/tenant baggage in MVP.
- **BackgroundTasks over Celery** — no broker dependency for self-host MVP.
- **Trimesh deferred** — not imported in Stage 1; STL/3MF metadata is filename-
  only until Stage 2 needs it for the viewer.
- **Source-mesh hash w/ G-code fallback** — best dedup quality without
  requiring slicer cooperation.
- **Soft delete only** — hard delete + GC is a Stage 4 concern.
- **Container-absolute paths in DB** — host path mapping is deployment-only.

---

## 12. When You Touch This System

- Adding a field to a model? Document it in §3, update `schemas/`, and add a
  test fixture under `backend/tests/fixtures/`.
- Adding an endpoint? Update §7, add OpenAPI `summary`/`description`.
- Changing the ingestion pipeline? Update §4 step list and add a regression
  test in `backend/tests/test_ingestion.py`.
- Anything that affects later stages? Note it under §11 with rationale.
