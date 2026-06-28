---
title: Spoolman
description: Connect a self-hosted Spoolman instance to track filament inventory and per-print consumption — off by default.
---

PrintStash integrates with [Spoolman](https://github.com/Donkie/Spoolman), a
self-hosted filament inventory manager. When connected, Spoolman stays the
**source of truth** for spools, filaments, and vendors: PrintStash *reads*
inventory for display, imports filament presets, lets you pick a spool per print,
and *writes measured consumption back*. It never reimplements the inventory
itself.

:::note
The integration is **optional and off by default**, and only a superuser can
configure it. Turn it on under **Settings → Spoolman**.
:::

## Connecting

Open **Settings → Spoolman** and fill in:

- **Base URL** — your Spoolman address, e.g. `http://spoolman.local:7912`.
- **API key** (optional) — only if Spoolman sits behind an authenticating proxy.
  Spoolman itself is keyless; PrintStash sends the key as both `Authorization:
  Bearer …` and `X-Api-Key` so either proxy style works.

Click **Save**, then **Test connection** to confirm reachability — a green
status badge and version appear when it's working. **Test connection** checks the
address currently in the form, so you can verify before saving.

### The base URL must be reachable from the *server*, not your browser

This is the most common setup snag. The connection is made by the **PrintStash
backend**, not your browser. So the base URL has to be reachable **from inside
the backend container** — which is a different network view from your laptop.

Avoid these, which only work from your browser (and fail with a *transport
error*):

- `http://localhost:7912` / `http://127.0.0.1:7912` — inside the container,
  `localhost` is the container itself, not the host.
- `http://192.168.0.1:7912` (or similar) — that's usually your **router**, not
  the machine running Spoolman.

Use an address the backend can route to:

| Situation | Base URL |
| --- | --- |
| Spoolman on the same Docker host, port published | `http://<docker-host-gateway>:7912` (often `http://172.17.0.1:7912`) |
| Spoolman on your LAN | the host's real LAN IP, e.g. `http://192.168.1.50:7912` |
| Spoolman as a container on the same Docker network | the service/container name and its **internal** port, e.g. `http://spoolman:8000` |

:::tip
The cleanest, most durable option is to put PrintStash and Spoolman on a **shared
Docker network** and reference Spoolman by container name (e.g.
`http://spoolman:8000`) — it survives container restarts and IP changes, unlike a
bridge-gateway IP.
:::

## Inventory

With the integration enabled and connected, the Spoolman card lists your spools
with their remaining weight, pulled live from Spoolman.

## Filament preset sync (Spoolman → PrintStash, one-way)

A **Sync from Spoolman** action on the Profiles page imports your Spoolman
filaments as PrintStash filament presets (deriving `$/kg` from price ÷ weight,
plus material, brand, density, and diameter). Sync also runs automatically when
you enable the integration.

- Synced presets are **read-only** in PrintStash — edit them in Spoolman.
- The first sync **adopts** matching local presets (by name + material) instead
  of duplicating them.
- Filaments removed in Spoolman are **unlinked** (reverted to editable local
  presets), never deleted.

This keeps filament data in one place instead of drifting across two apps.

## Per-print spool selection

When sending a job to a printer or logging a print manually, choose which
**spool** it consumes. The spool is saved on the print record and shown in the
model's print history. Prints that used a synced spool get **exact cost** (the
filament's real Spoolman price) and **more accurate weight** (the spool's real
density/diameter), instead of the static per-material estimate.

## Consumption write-back

When a **Moonraker-measured** print completes, PrintStash decrements the selected
spool by the measured grams used (server-side via Spoolman's `/spool/{id}/use`).
It runs once per job, after the job is committed, so it never blocks the print
path. Bambu reports no live consumption, so its prints are skipped.

Toggle this off with **Write consumption back to Spoolman** if you'd rather track
usage manually.

### Double-count safety

Moonraker has its own built-in Spoolman integration that can already decrement
the active spool. Before writing back, PrintStash checks Spoolman's active spool;
if Moonraker is already counting it, PrintStash **skips its own write** so a print
is never counted twice — and the UI warns you. If you've disabled Moonraker's
hook and want PrintStash to own consumption, enable the **Write back anyway**
override.

## Graceful degradation

A disabled or unreachable Spoolman never fails a request or blocks a print:
inventory reads return empty, write-back is skipped, and the connection state is
reported in `/health` for visibility (informational only — it never marks the
service degraded).
