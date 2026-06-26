# Manual Testing Checklist

Hands-on browser testing to run before tagging a release, on top of the
automated and smoke checks in [`release-validation.md`](./release-validation.md).
That doc covers clean install, SQLite upgrade, backend/frontend CI, and the
quick smoke list. This doc is the manual sweep of the UI workflows.

UI flows already exercised against a real backend by the Playwright suite in
`frontend/tests/e2e-real/` (`cd frontend && pnpm test:e2e:real`) are **not**
repeated here — this checklist is only the things that suite does not cover:
viewers, thumbnails, real printers, Spoolman, imports, statistics, shared
volumes, multi-role RBAC, and anything needing real hardware or files.

Run against a fresh `docker compose up -d --build` install (or a copy of a real
library for the upgrade path). Log in as the admin created at setup. Tick a box
only after you have seen the result yourself in the browser.

## 0. Setup & Auth

- [ ] `/setup` creates the first admin (storage backend, data dirs, backup
      retention, optional backup S3/R2 fields).
- [ ] `/login` signs in with username/password; write actions work afterward.
- [ ] Logged-out: write actions show a sign-in requirement, not a silent fail.
- [ ] Log in via `/api/v1/auth/login` with username + API key; confirm it works
      and stops working once the key is revoked.

## 1. Vault / Library

- [ ] `/` loads in grid and list modes; thumbnails render.
- [ ] Full-text search, tag filter, printer filter, printer-presence filter,
      and sort all change the result set.
- [ ] Drag a model into a collection, move a collection subtree, and
      recursive-delete a non-empty collection.
- [ ] Delete a tag that is assigned to models.
- [ ] Upload mesh-only and mesh+G-code together, with a name override, a
      collection assignment, an existing tag, and an inline new tag.
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
- [ ] Edit model collection, description, and tags (add/remove/inline-create);
      save and cancel both behave.
- [ ] Add a G-code revision; confirm the first one is auto-marked recommended.
- [ ] Mark another revision recommended; the previous marker clears.
- [ ] Set revision status (known_good / needs_test / failed / archived) and notes.
- [ ] Revision compare: pick two revisions, metadata shows side by side.
- [ ] Files tab lists source meshes separately from G-code.
- [ ] History tab: log a manual print (free-text printer name works), import
      Moonraker history for a matching file without duplicating jobs.
- [ ] Download a revision and the slicer-open action.

## 3. Printers

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

- [ ] Usage counts reflect matching files.
- [ ] Upload G-code and confirm filament/printer presets auto-detect; a preset
      the user has edited is not overwritten or renamed by detection.

## 6. Settings

- [ ] Overview: vault stats, counts, storage usage, health, version; CSV export.
- [ ] Storage: restore from a backup archive recovers the DB and files.
- [ ] Shared volumes: add a volume, run a manual scan, confirm files index in
      place; upload a revision and confirm write-back adds (never overwrites).
- [ ] Design: change model-card metric slots and confirm the reset actions work.
- [ ] Trash: purge-expired removes models past their retention.
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

- [ ] Create a link with a short expiry and confirm the public page 404s once it
      has expired.

## 9. RBAC (multi-user)

- [ ] Edit vs view roles: a view-only user cannot edit/delete; an edit user can.
- [ ] Make/remove admin, disable/enable a user, and reset a password.

## 10. Cross-cutting

- [ ] Theme switch (and theme-aware favicon).
- [ ] Mobile width: filter drawer and nav usable.
- [ ] No console errors during the above flows.
- [ ] Health endpoint version matches the tag being released.
