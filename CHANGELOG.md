# Changelog

## 0.6.2 - Shared volumes: scheduling + real-time watching

External Libraries grow up: the feature is now **Shared volumes** (a folder on
the server *or* a NAS), with proper scheduling and optional real-time syncing.

### Highlights

- **Cron-based scheduling.** Each volume's scan runs on a schedule you pick from
  a preset (hourly, every 6 hours, daily, weekly) or a custom cron expression —
  or set it to **Manual only**. This replaces the fixed "every N minutes" field;
  existing libraries are migrated to an equivalent cron schedule automatically.
- **Real-time watching.** Local folders are watched (via `watchfiles`) and
  reconcile within seconds of a change, so you no longer have to wait for the
  next scheduled scan. A burst of changes is debounced and then runs the same
  safe reconcile as a normal scan.
- **Network-aware fallback.** Filesystem events aren't delivered for network
  mounts (NFS/SMB/CIFS), so watching auto-detects the filesystem and falls back
  to scheduled scans on network folders. A per-volume control (Auto / On / Off)
  lets you override the detection. Each volume shows its detected filesystem and
  whether watching is active.

### Renamed

- The **Settings → NAS folders** tab is now **Shared volumes**, reflecting that
  it works for local server folders as well as NAS shares.

### Reliability

- **Fixed:** opening the Shared volumes settings tab returned a 500. The
  `watch_mode` column's migration default stored the lowercase enum value while
  SQLAlchemy reads enums by member name, so existing rows failed to load. The
  default is corrected and a follow-up migration repairs affected rows.

## 0.6.1 - About tab freshness

A small patch release.

### Highlights

- **Paste a model page to import.** Import from URL previously accepted only
  direct file/`.zip` links — pasting the Printables/MakerWorld/Thingiverse page
  you were looking at failed. The server now resolves the page to its
  downloadable asset (Printables, MakerWorld, and Thingiverse), keeping the
  original page as the model's source URL. MakerWorld/Thingiverse downloads that
  require a login accept an optional session cookie.

### Reliability

- **Fixed:** the Settings → About "Latest changes" card stayed on the previous
  release because its entry list was hand-maintained and easy to forget. A
  drift-guard test now fails whenever `changelog.ts` falls behind
  `package.json`, so the About tab can't ship stale.

### Performance

- **Fixed:** 3D model (STL) previews took ~20-30s to load on the first open.
  The `/files/{id}/stl` endpoint wrapped the rendered bytes in a
  `StreamingResponse(BytesIO(...))`, which Starlette iterates line-by-line —
  catastrophic for binary mesh data, where stray `0x0A` bytes split the body
  into tens of thousands of tiny ASGI chunks (~1s per MB). It now returns the
  body in a single `Response`, dropping an 11 MB preview from ~26s to ~0.02s.
  Affects both the model detail viewer and public share links.

## 0.6.0 - NAS External Libraries

Mirror a folder you already have — typically on a NAS — into PrintStash without
copying it. The folder stays the source of truth; PrintStash indexes files
where they live and stores only thumbnails and metadata.

### Highlights

- **External libraries (NAS folder mirroring).** Point PrintStash at a folder
  and it indexes every supported file in place (`File.is_external`), storing
  only the generated thumbnail + metadata. Opt-in and OFF by default
  (`SystemConfig.external_libraries_enabled`). Manage libraries in Settings
  (superuser only).
- **Two-way sync.** A scan reconciles the index with the folder — new files
  indexed, removed files trashed, edited files re-hashed and refreshed — while
  web uploads/revisions *write back* into the folder so it stays complete.
  Revisions follow their model's library automatically; new uploads pick a
  destination in the upload modal.
- **Folder hierarchy → collections.** In MIRROR mode a file's subfolder chain
  becomes its collection path; SINGLE mode routes everything into one chosen
  collection.
- **Your bytes are never touched.** PrintStash only ever *adds* files to the
  folder (collision-safe naming), never overwrites. Trash hard-delete and the
  orphan-blob GC skip external files entirely — removing a model or a library
  drops the index rows but leaves the originals on the NAS.
- **Unmount safety.** A scan aborts without deleting anything when the root is
  missing/unreadable, or empty while indexed files still exist — an unmounted
  share can never trigger mass deletion.
- **Periodic background scans.** Enabled libraries are rescanned on their
  configured interval; manual scan available via the API and UI.

### Reliability

- **Fixed:** the periodic scan scheduler crashed on a naive/aware datetime
  comparison (`last_scanned_at` reads back from the DB without tzinfo), which
  the scan loop swallowed — silently stopping scheduled scans after each
  library's first run. Normalised via `core.time.ensure_utc`.
- **Fixed:** the frontend e2e suite broke once the upload modal began probing
  `/api/v1/config` for the NAS feature flag — the mock API now serves the vault
  config (and `/libraries`), and a new e2e case covers the upload modal's NAS
  write-back destination selector.
- Real-use-case test suites for NAS mirroring (safety invariants, write-back,
  reconcile, scheduler, full API round trip) and for ingestion/revisions driven
  by real STL/3MF/g-code fixtures. Frontend unit tests pin the External
  Libraries API client and the `external_libraries_enabled` config flag.

## 0.5.0 - Import, CAD, Sharing & Measured Prints

A big release closing the ingest/discovery gap and deepening the
print-tracking loop that sets PrintStash apart.

### Highlights

- **Import from URL or ZIP.** Paste a direct file/`.zip` URL or upload a `.zip`
  and pick which files to import. Each 3D file becomes its own model, grouped
  under an auto-created collection named after the archive. Server-side fetches
  are SSRF-guarded (no private/loopback/metadata hosts) and archives are
  zip-slip / zip-bomb protected.
- **STEP / STP CAD files.** Ingested, tessellated (via `cascadio`/OpenCASCADE),
  previewed in the browser, and thumbnailed like any mesh.
- **Public share links.** Create expiring, read-only links to a single model.
  View-only by default (the viewer renders a tessellated mesh; original-file
  download is opt-in per link). Strictly isolated: an unauthenticated, GET-only
  router; tokens stored hashed; uniform 404 on bad/expired/revoked tokens; file
  access re-scoped to the shared model; per-IP rate limiting.
- **Measured filament + duration.** When a print finishes, real filament used
  and actual duration are captured from Moonraker and shown in print history,
  with real per-print cost (Bambu leaves filament null — no live data).
- **Auto known-good revisions.** A revision is promoted to *known-good* after its
  first successful print (never overriding a manual failed/archived verdict).
  Toggle in Settings → Design.
- **Delete G-code revisions.** The Revisions tab gains a delete action per
  revision. Deletes are soft — the file follows the trash lifecycle and its blob
  is reclaimed by the GC — consistent with model deletion.
- **Print history without a registered printer.** Manual print records can now be
  logged against a free-text printer name ("Other (not listed)…") instead of
  requiring a preconfigured Moonraker/Bambu printer. `print_jobs.printer_id` is
  now nullable, backed by a new `printer_name` column.

## 0.4.0 - Vite + React Router Frontend

The frontend is rebuilt as a Vite single-page app on React Router, migrated off
Next.js. The app was already ~95% client-rendered behind auth, so server
rendering added complexity without benefit — and under multi-user RBAC it broke
outright, because server-side renders had no access to the browser-held token.

### Highlights

- Frontend migrated from Next.js to Vite + React Router (client SPA). All reads
  now fetch client-side with the stored token.
- Fixes the model detail page server error and the broken 3D preview / file
  downloads that appeared once assets required authentication.
- TanStack Query is the cache layer: shared `collections`/`tags` cache across the
  grid, detail, and upload views; revalidation on window focus (so another
  user's edits surface); and automatic refetch after any mutation.
- Production image now serves the static build via nginx, which proxies
  `/api/v1` and WebSockets to the API same-origin (replacing the Next rewrites).
- Tooling moved to Vite build, `tsc` typecheck, and a standard ESLint flat
  config.

## 0.3.0 - Multi-User & RBAC

PrintStash gains real multi-user support with per-collection access control.

### Highlights

- Collection-level role-based access control: each user can be granted `view`,
  `edit`, or `admin` on a collection, and the UI gates actions accordingly.
- Admin user management and access controls.
- Authenticated asset delivery: thumbnails, mesh/STL previews, and file
  downloads now require a signed-in user and carry the access token.
- Lossless WebP thumbnails.
- Settings UI refinements and collections sidebar (outliner) fixes.

### Upgrade Notes

Read [UPGRADE.md](./UPGRADE.md) before upgrading an existing install.

## 0.1.0 - Initial Self-Hosted Release

PrintStash 0.1 is the first tagged self-hosted release. It is focused on the
local-first library workflow: ingest STL/3MF/G-code, extract slicer metadata,
keep model revisions searchable, and integrate with Moonraker/Klipper printers.

### Highlights

- Docker Compose is the primary install path, with SQLite and local disk as the
  default storage stack.
- Alembic migrations provide a repeatable schema upgrade path.
- OrcaSlicer post-processing ingestion remains dependency-free and exits `0` on
  vault outages.
- G-code revisions support labels, outcome status, notes, recommended versions,
  and metadata comparison.
- Model detail includes split overview/files/revisions/history/settings views,
  mesh preview, and a client-side G-code toolpath viewer.
- Settings includes vault stats, storage usage, metadata/card display
  preferences, API-key management, backup creation, and trash restore/purge.
- Model print history supports manual entries and Moonraker history import for
  matching G-code filenames.
- Moonraker/Klipper is the primary supported printer provider.
- Bambu LAN is available as beta status/control support only. Upload, send, start,
  and file inventory parity are intentionally not part of 0.1.
- Postgres, S3/R2 storage, cloud backups, and audit logs are optional adapters for
  larger self-hosted installs.

### Validation

- Backend unit/API suite covers ingestion, auth, migrations, parser fixtures,
  thumbnails, storage/file serving, printer providers, print jobs, and API
  hardening.
- Frontend CI runs typecheck, lint, and production build.
- Additional parser fixtures cover OrcaSlicer, PrusaSlicer, Bambu Studio, Cura,
  and a common Klipper/Orca profile.

### Upgrade Notes

Read [UPGRADE.md](./UPGRADE.md) before upgrading an existing install.
