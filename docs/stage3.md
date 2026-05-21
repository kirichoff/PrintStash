# Stage 3 — The Hub

Bidirectional integration with Klipper/Moonraker printers.

## Backend

- New tables: `printer`, `print_job` plus enums `printer_status`, `print_job_state`.
- `app/services/moonraker.py` — async `MoonrakerClient` (HTTP REST: `info`, `query_objects`,
  `upload_gcode`, `pause/resume/cancel`) and a persistent `MoonrakerSubscription` WS
  subscriber with auto-reconnect.
- `app/services/printer_hub.py` — process-wide `hub` singleton that:
  - boots one subscription per printer on app startup (via lifespan),
  - keeps an in-memory `snapshot` cache of the latest `print_stats`, `virtual_sdcard`,
    `extruder`, `heater_bed`, `webhooks` objects per printer,
  - fans out updates to attached browser WebSockets,
  - reconciles `PrintJob` state from `print_stats.state` matched by `remote_filename`.
- New router `app/api/v1/printers.py`:
  - `GET /api/v1/printers`, `GET /printers/{id}`
  - `POST /printers`, `PATCH /printers/{id}`, `DELETE /printers/{id}` (API-key)
  - `POST /printers/{id}/send` — uploads a vault G-code File to Moonraker,
    optionally starts the print, records a `PrintJob`.
  - `POST /printers/{id}/{pause|resume|cancel}` (API-key)
  - `GET /printers/{id}/status` — cached snapshot + printer row
  - `GET /printers/{id}/jobs` — recent print history
  - `WS /printers/{id}/ws` — live `{type, printer_id, data}` stream

### Error contract for `/send`

| Status | Detail               | Meaning                                       |
|--------|----------------------|-----------------------------------------------|
| 404    | `printer_not_found`  | Unknown printer id                            |
| 404    | `file_not_found`     | Unknown file id                               |
| 400    | `file_not_gcode`     | File exists but isn't a G-code artifact       |
| 410    | `file_blob_missing`  | DB row exists but the on-disk blob is gone    |
| 502    | `moonraker_error: …` | Moonraker rejected the upload / start request |

## Taxonomy

- Hierarchical categories: `category` table with `parent_id` + materialised `path`
  (e.g. `functional/brackets`). Model rows carry both `category` (path) and `category_id`.
- Flat tags via `tag` + `model_tag_link`.
- `GET /api/v1/categories` and `GET /api/v1/tags` expose facets with model counts.
- `GET /api/v1/models?category=functional&tag=printable&tag=v2` filters by category
  *prefix* (so `functional` matches `functional/brackets/foo`) and by **all** tags (AND).
- Ingestion auto-creates missing categories/tags via `services/taxonomy.py`.

## Thumbnails

- `services/mesh_processing.py` rewritten as a pure-CPU numpy+Pillow software
  renderer — no Trimesh/matplotlib needed in the render path, so STL/3MF uploads now
  always produce a thumbnail.
- `Model.thumbnail_file_id` joins to the File whose preview was extracted; legacy
  `thumbnail_path` is still served as a fallback.

## Frontend

- `lib/api.ts` extended with category, tag, printer, send, control, status, jobs, and
  WebSocket helpers (`openPrinterWS`). Browser-side WS URL comes from
  `NEXT_PUBLIC_WS_URL` (rewrites don't proxy WS).
- `components/filter-sidebar.tsx` — recursive category tree with model counts +
  clickable tag chips.
- `/` rebuilt as `ModelBrowser` (client component) — sidebar drives server-side
  filtering via the existing `/models` endpoint.
- `/printers` — list + add-printer modal.
- `/printers/[id]` — live status (progress bar, temps, controls), reconnecting WS,
  print history table.
- Model detail page now has a **Send to printer** button (visible only when the model
  has at least one G-code file).
- Header nav gains a *Printers* entry.

## SQLite schema migration

We're still pre-Alembic. `db/session.py::_apply_column_patches()` hand-rolls
`ALTER TABLE` for the new columns on existing databases; new tables come from
`SQLModel.metadata.create_all()`.

## Open items

- Test coverage for Moonraker client + hub (mocked WS).
- WS auth: currently any client can attach. Stage 4 will gate via JWT.
- Bulk re-render thumbnails CLI for vaults migrated from Stage 1/2.
