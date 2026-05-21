# Stage 1 — The Headless Vault (execution log)

This document tracks every meaningful change made during Stage 1 development.
Append a bullet under the relevant section when you ship work.

---

## Goals

- FastAPI core with SQLModel + SQLite, packaged as a single Docker service.
- Three persistent volumes (blobs, thumbs, db) for clean backups + future S3 swap.
- `POST /api/v1/ingest/orca` accepting OrcaSlicer multipart uploads.
- Background pipeline: hash → parse → thumbnail → dedup → persist.
- OrcaSlicer post-processing script (stdlib only, fail-soft).
- Full OpenAPI surface — Swagger is the only UI in Stage 1.

---

## Build Log

### 2026-05-11 — Stage 1 scaffolding
- Created repository layout per AGENTS.md §4.
- Added `backend/app/core/{config,logging,security}.py` — env-driven settings,
  stdlib logging configurator, shared `X-API-Key` dependency.
- Added `backend/app/db/{models,session}.py` — `Model` / `File` / `Metadata`
  SQLModel tables; SQLite engine with `check_same_thread=False`.
- Added `backend/app/services/`:
  - `hashing.py` — streaming sha256 (1 MiB chunks).
  - `storage.py` — slugify, unique-slug helper, canonical path layout, stream-to-disk.
  - `gcode_parser.py` — head+tail window read, regex map for OrcaSlicer comments,
    duration parser ("1h 23m 45s" → seconds).
  - `thumbnail.py` — PNG extraction from base64 blocks, picks largest.
  - `jobs.py` — in-memory `JobRegistry` (Stage 1 only).
  - `ingestion.py` — full background pipeline.
- Added `backend/app/api/v1/` routers: `health`, `ingest`, `models`, `files`.
- Added `backend/main.py` with FastAPI lifespan that calls `ensure_dirs()` +
  `init_db()`.
- Added `backend/Dockerfile` (python:3.11-slim, curl for healthcheck).
- Added `docker-compose.yml` with three named volumes + healthcheck.
- Added `scripts/nexus3d_orca_push.py` (stdlib-only, exit-0 always).
- Added `.opencode/skills/nexus3d-vault/SKILL.md` as the architectural source of truth.
- Added `AGENTS.md` with conventions, non-negotiables, and runbook.

---

## Known Issues / Resolved

- *(none yet)*

---

## Deferred to Later Stages

- **Stage 2:** trimesh-backed STL/3MF geometry stats, Next.js UI, R3F viewer.
- **Stage 3:** Moonraker bridge, Celery/Redis for jobs, send-to-printer.
- **Stage 4:** OAuth2/JWT, Postgres + Alembic, S3 adapter, hard-delete + GC.
