---
title: User guide
description: "The everyday loop: add files, check them, mark what worked, find them later."
---

This is the normal PrintStash loop: add files, understand what you have, and find
the right one later. It describes what the app does today. If terms like
*model*, *artifact*, or *recommended revision*, skim
[Core concepts](/PrintStash/concepts/core-concepts/) first.

The questions this loop answers:

- What did I slice, and when?
- Which G-code revision was the one that came out right?
- What slicer, material, and printer settings produced it?
- What does the toolpath actually look like?
- Where is it — and is the printer ready for it?
- Can I get my metadata back out?

## 1. Get a model in

Open the vault grid (`/`). A fresh install is empty, so start with one model you
know well.

Open the upload modal and drop in an STL or 3MF. Pick a collection there,
for example `Functional/Brackets`, and add tags inline if they do not exist yet.
The upload runs in the background and appears in the task center while the
thumbnail renders. When it finishes, a model card appears in the grid.

You don't have to upload mesh and G-code together. The modal accepts mesh-only,
G-code-only, or both at once — whatever you have on hand.

## 2. Add G-code and watch metadata appear

Upload a G-code file for that same model. Open the model detail page and look at
the **Overview** tab: PrintStash has read the slicer comments and filled in the
slicer name, layer height, infill, material, estimated print time, filament
weight/length, and printer model where the slicer recorded it. This works across
OrcaSlicer, PrusaSlicer, Bambu Studio, Cura, and Klipper/Orca-style profiles —
though exactly which fields appear depends on what your slicer wrote, so blanks
are normal.

Now look at the two viewers:

- **3D model** — the mesh, with solid / x-ray / wireframe modes, fit-to-view,
  a build-plate grid, zoom, and a screenshot button. 3MF and OBJ are converted to
  a cached STL for preview; STL streams directly.
- **G-code toolpath** — the sliced path for the latest/recommended G-code. Scrub
  the layer slider, toggle travel moves, and turn on the bed overlay (drawn from
  known printer profiles).

The toolpath viewer is for recognition, not certification. It will not validate
macros, acceleration, pressure advance, or firmware-specific behavior.

## 3. Build the revision story

This is the part that replaces guessing from filenames.

- Upload a second G-code revision, or edit the fields on an existing one in the
  **Revisions** tab.
- Set each revision's status — `needs_test`, `known_good`, or `failed`.
- Drop a short note you will understand later: `PETG, +5°C`,
  `tighter fit`, `warped at corners`.
- Mark the best one **recommended**. Remember the invariant: marking one
  recommended clears the marker from the rest, so there's always exactly one
  good answer.
- Use **compare** to put two revisions' slicer/material/print settings side by
  side when you're trying to remember what you changed.

Then log how it actually printed. The **History** tab takes manual print-job
entries, or — if you've connected a Moonraker printer — imports matching history
straight from the printer (see step 5).

## 4. Find it again

Later, back at the grid:

- Search by model name.
- Filter by collection (breadcrumbs let you drill into the tree) or by tag.
- Filter by printer presence to see what's already loaded where.

The model keeps its mesh, revisions, notes, and history together, so finding it
again is one search instead of a dig through old export folders.

## 5. Connect a printer

Add a Moonraker/Klipper printer from **Printers** and open its detail page. From
there, watch live status, send a vault G-code file to it, sync its remote
file inventory, and import its print history onto the matching models.

Open the **Diagnostics** tab to see the provider's support level, capability
checks, and which actions aren't supported. PrintStash is Moonraker-first; Bambu
LAN is beta and limited to status plus pause/resume/cancel. The full breakdown is
in [Printers & providers](/PrintStash/guides/printers/).

## 6. Get your data back out

Your library should not be a trap. From **Settings → Overview**, export
metadata as JSON or CSV. JSON keeps the full library context; CSV gives one row
per stored file. Exports include model fields, collections, tags, revision data,
and slicer/mesh metadata.

They deliberately **exclude** the raw STL/G-code blobs, secrets, and printer
credentials — and they require auth, because filenames, materials, and print
history can leak more about a job than you'd expect. For moving or recovering an
entire install (blobs and all), use full
[backup & restore](/PrintStash/guides/backup-and-restore/) instead.

## Skip the manual upload: the OrcaSlicer hook

Once manual upload feels annoying, use the OrcaSlicer hook. PrintStash ships a
post-processing script (`scripts/printstash_orca_push.py`) that you add to
OrcaSlicer's post-processing settings. After every slice, OrcaSlicer runs it and
the exported G-code lands in the vault as a new revision.

A couple of things that make it pleasant to live with:

- It uses only the Python standard library — nothing to `pip install`.
- It authenticates with your username and a PrintStash **API key** (create one
  under **Settings → Access**), not your password.
- If PrintStash is offline, it exits `0` — so a down vault never breaks your
  slicing or export.

Point it at your upload endpoint with the API key. After that, new revisions
show up when you export.
