# Roadmap

This is the working roadmap for PrintStash. It is intentionally practical: the
project should stay useful for home labs, single printers, and small farms before
it grows into anything heavier.

Roadmap feedback belongs in
[the public roadmap discussion](https://github.com/xiao-villamor/PrintStash/discussions/1).
Issues are better for confirmed bugs or scoped implementation work.

## Current Release: 0.6.x — Self-Hosted Library

Production hardening is in place. The app is useful for local-first 3D print
library workflows, installable through Docker Compose (the default compose pulls
prebuilt GHCR images; a build overlay is available for contributors), and ready
for real homelab feedback. SQLite plus local filesystem storage remain the
default path. Postgres, S3/R2-compatible storage, cloud backups, and provider
adapters are available as optional deployment paths.

Developed features in the current app:

- STL, 3MF, OBJ, STEP/STP, and G-code ingestion through the web UI, REST API, and OrcaSlicer post-processing hook
- Import from URL or `.zip` (including Printables/MakerWorld/Thingiverse model pages resolved to their downloadable asset), SSRF-guarded and zip-slip/zip-bomb protected
- Shared volumes: mirror a server folder or NAS in place with two-way write-back, per-volume cron scheduling, and optional real-time watching with network-aware fallback
- Public, expiring, read-only share links to a single model (view-only by default; opt-in original-file download)
- Print statistics dashboard (cost, filament, prints, print time; time series + top collections/filaments) with a configurable display currency
- Measured prints: real filament + duration and per-print cost captured from Moonraker, with auto known-good revision promotion
- G-code parser coverage for OrcaSlicer, PrusaSlicer, Bambu Studio, Cura, and Klipper/Orca samples
- Content-hash deduplication, logical model grouping, version history, thumbnails, cached STL conversion for 3MF/OBJ preview, and in-browser mesh/G-code previews
- Categories, tags, search, model editing, printer-presence filters, model-to-printer file badges, collection counts, collection moves, and drag-and-drop library organization
- G-code revision upload, per-revision labels, outcome status, notes, recommended marker, and side-by-side metadata comparison
- Filament and printer profiles (presets) for cost tracking and slicer defaults, managed from a dedicated Profiles page
- "Open in slicer" deep-links for OrcaSlicer, Bambu Studio, and PrusaSlicer straight from a model file
- Model print history with automatic Moonraker import for matching filenames and manual print-job logging
- First-run setup wizard, JWT auth for UI/scripts, refresh/logout flow, per-user API keys, role-aware admin access, and audit logs
- Alembic migrations, optional Postgres support, SQLite-to-Postgres migration script, and documented upgrade flow
- Local and optional S3/R2 storage, multipart S3 uploads, pre-signed downloads, cached mesh conversion, lifecycle policy configuration, and backup/restore endpoints
- Vault stats, storage usage reporting, configurable card metrics, trash retention controls, restore/purge actions, and thumbnail rebuild jobs
- Prometheus `/metrics` endpoint (request latency, ingestion counts, live printer status) and operational health output for database, storage, backup, background jobs, external-library scans, and printer provider readiness
- Moonraker/Klipper provider with live status, upload/send, optional start, pause/resume/cancel, printer file inventory sync, remote-file start, and job history
- Bambu LAN beta provider with local status plus pause/resume/cancel controls; upload/send, remote file inventory, and remote-file start remain unsupported
- Responsive Vite/React UI with a light/dark theme toggle (system-preference aware), mobile bottom navigation, slide-out nav/filter drawers, and a floating action button across the library, model detail, upload, taxonomy, profiles, settings, setup, and printer workflows

The releases below are intentionally small: each is meant to be a single,
shippable step rather than a multi-month epic. Versions are indicative, not
promises, and the order can shift with real-world feedback.

## 0.6.x — Release Validation and Feedback (in progress)

Goal: keep the self-hosted release easy to install, easy to upgrade, and safe
enough for real home use.

- Publish and validate tagged release notes and Docker image guidance
- Collect real-world feedback from Docker/NAS/homelab installs
- Exercise backup/restore, upgrade, and provider diagnostics on fresh installs
- Add parser fixtures from more slicers and printer profiles as users share samples
- Improve first-run setup and error messages where new users get stuck
- Scheduled release backup/restore smoke checks
- Upgrade notes for SQLite and optional Postgres installs

## 0.7 — Notifications and Event Hooks

Goal: tell people when something happens without making them watch a dashboard.

- Generic outbound webhooks for print-completed, print-failed, print-cancelled, and printer-offline events (cancellations are a distinct event so they can be muted separately)
- First-party targets: Discord, Telegram, and ntfy
- Per-event and per-printer notification toggles
- Delivery retry and a visible "last notification" status

## 0.8 — Filament and Spool Inventory

Goal: track what filament you actually have and what each print consumes.

- Spool inventory with material, color, weight, and cost
- Auto-decrement spool weight from measured prints (reuses Moonraker filament data)
- Low-stock indicators and per-spool usage history
- Optional Spoolman integration for people who already run it

## 0.9 — Provider Maturity (Bambu + reliability)

Goal: make printer integrations predictable across normal home setups.

- Bambu LAN upload/send parity, with provider-safe guardrails
- More disconnect/reconnect coverage for mixed fleets
- Clear UI states for unsupported printer actions
- Broader hardware validation and notes for tested Moonraker and Bambu setups

## 0.10 — More Providers

Goal: cover the other common homelab print stacks.

- OctoPrint provider (status, send, basic controls)
- PrusaLink / Prusa Connect provider
- Shared provider capability matrix so the UI shows exactly what each one supports

## 0.11 — Library Workflow Polish

Goal: make the vault better as a daily-use 3D print library.

- Better bulk editing for tags/categories and revision labels
- Saved filters or views for common searches, plus favorites/starred models
- Richer model/version comparison beyond the current G-code metadata compare
- More useful model detail pages for repeated reprints, including deeper print-history analytics
- Import/export paths for people migrating from folders or other tools

## 0.12 — Fleet and Scheduling

Goal: help small printer farms without turning PrintStash into a full slicer or
queue manager.

- Queue visibility with a provider-normalized job model
- Optional routing strategies: manual, default printer, least busy
- Printer maintenance windows, soft-drain mode, and a simple maintenance log

## 0.13 — Auth and Platform

Goal: fit cleanly into existing homelab infrastructure.

- OIDC / SSO login (Authentik, Authelia, and similar)
- Installable PWA / improved mobile experience
- Localization (i18n) scaffolding

## Later — Optional Cloud-Ready Adapters

Goal: support larger installs while keeping the default path self-hosted and
local-first.

- More complete Postgres deployment guidance
- S3/R2 lifecycle policy templates
- Multi-tenant/org routing only if there is real demand
- Cloud printer/provider adapters only when they do not compromise local-first use

## Not Planned Right Now

- A slicer
- A public cloud service
- Hard dependency on Postgres, Redis, S3, or external queues
- Replacing Moonraker/Bambu firmware as the source of truth for print execution
