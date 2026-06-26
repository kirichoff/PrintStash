# Manual Testing Checklist

Hands-on browser testing to run before tagging a release, on top of the
automated and smoke checks in [`release-validation.md`](./release-validation.md).
That doc covers clean install, SQLite upgrade, backend/frontend CI, and the
quick smoke list. This doc is the full manual sweep of the UI workflows.

Run against a fresh `docker compose up -d --build` install (or a copy of a real
library for the upgrade path). Log in as the admin created at setup. Tick a box
only after you have seen the result yourself in the browser.

## Automated coverage

Items marked **✅ automated** are exercised against a real backend + database by
the Playwright suite in `frontend/tests/e2e-real/` — run it with:

```bash
cd frontend && pnpm test:e2e:real
```

When that suite is green you can skip the ✅ items and focus this manual pass on
the rest: 3D/G-code viewers, thumbnails, real printers, Spoolman, imports,
statistics, shared volumes, mobile, and anything needing real hardware or files.

## 0. Setup & Auth

- [ ] `/setup` creates the first admin (storage backend, data dirs, backup
      retention, optional backup S3/R2 fields).
- [ ] `/login` signs in with username/password; write actions work afterward.
- [ ] Logged-out: write actions show a sign-in requirement, not a silent fail.
- [ ] **✅ automated** — Settings → Users & Access: create an API key, copy the
      one-time secret, then revoke it. (Manual extra: log in via
      `/api/v1/auth/login` with username + API key and confirm it stops working.)

## 1. Vault / Library

- [ ] `/` loads in grid and list modes; thumbnails render.
- [ ] Full-text search, tag filter, printer filter, printer-presence filter,
      and sort all change the result set.
- [ ] **✅ automated** — create a collection (and a nested subcollection), delete
      an empty collection, delete a child then its parent. (Manual extra: drag a
      model into a collection, move a subtree, recursive-delete a non-empty one.)
- [ ] **✅ automated** — create and delete a tag. (Manual extra: deleting a tag
      assigned to models.)
- [ ] **✅ automated** — upload a G-code-only model and see it land in the
      library. (Manual extra: mesh-only and mesh+G-code together, name override,
      collection assignment, existing tag, inline new tag.)
- [ ] Upload a `.zip`; pick a subset of files on extraction; confirm each 3D
      file becomes its own model under an auto-created collection.
- [ ] URL import of a single file and of a model page (Printables/MakerWorld/
      Thingiverse) — source URL is kept, asset is fetched.
- [ ] Task center shows queued → running → completed (and a failed case).

## 2. Model Detail

- [ ] `/models/{id}` opens; viewer shows the mesh.
- [ ] 3D viewer: solid, X-ray, wireframe, fit-to-view, grid, zoom, reset,
      screenshot.
- [ ] G-code toolpath mode: layer slider, travel toggle, bed overlay.
- [ ] 3MF/OBJ/STEP open via the cached STL preview path.
- [ ] **✅ automated** — edit the model name and save. (Manual extra: collection,
      description, tags add/remove/inline-create, and cancel.)
- [ ] Add a G-code revision; confirm the first one is auto-marked recommended.
- [ ] Mark another revision recommended; the previous marker clears.
- [ ] Set revision status (known_good / needs_test / failed / archived) and notes.
- [ ] Revision compare: pick two revisions, metadata shows side by side.
- [ ] Files tab lists source meshes separately from G-code.
- [ ] History tab: log a manual print (free-text printer name works), import
      Moonraker history for a matching file without duplicating jobs.
- [ ] Download a revision and the slicer-open action.

## 3. Printers

- [ ] **✅ automated** — `/printers` add a Moonraker printer and remove it.
- [ ] Add a Moonraker/Klipper printer (mock or real); status reaches online.
- [ ] `/printers/{id}`: live/reconnecting WebSocket state, snapshot metrics.
- [ ] Status tab: current file, progress, temps; pause/resume/cancel (if safe).
- [ ] Files tab: sync remote inventory, vault-match links, start a remote file.
- [ ] Jobs tab: print-job history populates.
- [ ] Diagnostics tab: support level, capability/connectivity checks, rerun.
- [ ] Send a vault G-code to a printer from model detail (Klipper sync panel).
- [ ] (If available) Add a Bambu LAN printer; status + pause/resume/cancel only.

## 4. Statistics (admin)

- [ ] `/statistics` loads with completed-print data.
- [ ] Period selector (7d/30d/90d/1y/all) drives the whole page.
- [ ] Metric cards, time series (area/line/bar switch), top collections, top
      filaments all render; empty state shows for an empty period.
- [ ] Cost figures use the currency set in Settings → Design.

## 5. Profiles

- [ ] **✅ automated** — `/profiles`: create, edit (auto-save), and delete a
      filament preset and a printer preset.
- [ ] Usage counts reflect matching files.
- [ ] Upload G-code and confirm filament/printer presets auto-detect; a preset
      the user has edited is not overwritten or renamed by detection.

## 6. Settings

- [ ] **✅ automated** — Overview: export JSON. (Manual extra: vault stats,
      counts, storage usage, health, version; CSV export.)
- [ ] **✅ automated** — Storage: trigger a full backup and see it listed.
- [ ] Shared volumes: add a volume, run a manual scan, confirm files index in
      place; upload a revision and confirm write-back adds (never overwrites).
- [ ] **✅ automated** — Design: change the currency (persists) and toggle a
      metadata visibility field (persists across reload). (Manual extra:
      model-card metric slots and the reset actions.)
- [ ] **✅ automated** — Trash: soft-delete a model, restore it, then purge it.
      (Manual extra: purge-expired.)
- [ ] About: version matches the release; changelog renders.

## 7. Spoolman (if enabled)

- [ ] Settings → Spoolman: set base URL/API key, Test connection passes,
      `/health` spoolman component reports reachable.
- [ ] Sync filaments; linked presets are read-only (edit/delete rejected).
- [ ] Select a spool on send-to-printer / manual log; it persists in history.
- [ ] After a Moonraker-measured completion, the spool decrements once.
- [ ] Native-hook detection warning shows and write-back defaults off when the
      Moonraker active-spool hook is present.

## 8. Public Share Links

- [ ] **✅ automated** — create a read-only link (download blocked) and a
      downloadable link; revoke a link and confirm the public page 404s and the
      link drops off the management list. (Manual extra: expiry behaviour.)

## 9. RBAC (multi-user)

- [ ] **✅ automated** — create a non-admin user, grant them access to one
      collection, and confirm that user sees only the granted collection.
- [ ] Manual extra: edit vs view roles (view cannot edit/delete), make/remove
      admin, disable/enable a user, reset a password.

## 10. Cross-cutting

- [ ] Theme switch (and theme-aware favicon).
- [ ] Mobile width: filter drawer and nav usable.
- [ ] No console errors during the above flows.
- [ ] Health endpoint version matches the tag being released.
