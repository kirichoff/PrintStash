# Stage 4 — Production Hardening

**Codename:** Production Hardening
**Status:** active

## Goal

Ship the first stable self-hosted release. Stage 4 prioritises safe upgrades,
predictable recovery, stronger authentication, deletion lifecycle controls,
and clearer deployment choices. SQLite and local filesystem storage remain the
default path; Postgres and S3 stay optional adapters for larger installs.

---

## Execution Log

### Phase 4a — Schema and upgrade safety

- [x] Reframe Stage 4 around self-hosted production hardening
- [x] Add Alembic to the backend and create a baseline migration
- [x] Remove ad hoc SQLite column patching as the schema upgrade mechanism
- [ ] Document an explicit upgrade flow for Docker and local installs
- [ ] Add migration smoke tests against SQLite
- [ ] Add Postgres drivers (`asyncpg`, `psycopg2`) to `pyproject.toml`
- [ ] Implement `async_session()` on `SessionFactory` Protocol
- [ ] Create `create_async_engine()` in `db/session.py`
- [ ] Add Postgres service to `docker-compose.yml` as an optional profile
- [ ] Write a SQLite→Postgres migration guide/script

### Phase 4b — Auth and admin hardening

- [ ] Add `RefreshToken` model (token hash, user_id, expires_at, revoked)
- [ ] Implement `POST /auth/refresh` and `POST /auth/logout` endpoints
- [ ] Replace raw `Header` auth with FastAPI's `OAuth2PasswordBearer`
- [ ] Add role-based access: enforce `is_superuser` on admin endpoints
- [ ] Add `scope` to JWT payload (read/write/admin)
- [ ] Implement in-memory token blocklist (invalidated on logout)

### Phase 4c — Data lifecycle and recovery

- [ ] Add `deleted_at` column to File, Printer, PrintJob, User, Tag, Category
- [ ] Add `deleted_by` FK to User on all soft-deletable tables
- [ ] Implement `DELETE` endpoints for printers, categories, tags, users (soft)
- [ ] Implement `POST /{resource}/{id}/restore` endpoints
- [ ] Implement hard-delete endpoint: `DELETE /admin/{resource}/{id}?hard=true`
- [ ] Implement scheduled GC background task (purge rows with `deleted_at < retention`)
- [ ] Implement orphan file cleanup (delete blobs when DB records are purged)
- [ ] Harden local backup + restore workflows and document recovery steps

### Phase 4d — Audit and observability

- [ ] Add `AuditLog` model (actor_id, action, resource_type, resource_id, diff JSON, ip, timestamp)
- [ ] Add `created_by` / `updated_by` columns to Model, Printer, PrintJob, Category, Tag
- [ ] Implement SQLAlchemy event listener for auto-audit on writes
- [ ] Implement `GET /api/v1/admin/audit` endpoint (admin-only, filterable)
- [ ] Add audit log pagination and filtering by resource/resource_id

### Phase 4e — Optional deployment adapters

- [ ] Add Postgres deployment docs with clear “when to choose it” guidance
- [ ] Add S3/S3-compatible deployment docs with clear “optional feature” guidance
- [ ] Add S3 health check probe to `/api/v1/health`
- [ ] Implement multipart upload for files > 50MB in `S3StorageBackend`
- [ ] Implement pre-signed URL generation for direct downloads
- [ ] Add MinIO service to `docker-compose.yml` for local dev/test
- [ ] Implement bucket lifecycle policy configuration (expiration, tiering)

---

## Deferred beyond first stable release

- Multi-tenant organizations and workspace routing
- Automatic tenant scoping on every query
- Cloud-first storage namespacing and org-aware object layout

These remain valid future directions, but they are not part of the first
stable self-hosted release.

---

## Pre-existing foundation carried from Stages 1–3

| Component | Status |
|---|---|
| `S3StorageBackend` (all 16 methods) | 85% complete |
| `SessionFactory` Protocol with `async_session()` stub | Ready |
| SQLModel on all tables (Postgres-compatible) | Done |
| Basic JWT login (`/login`, `/me`, bcrypt) | Done |
| `system_config` runtime overlay (DB-backed config) | Done |
| Soft-delete on Model (`deleted_at` column) | Done |
| Backup S3 (separate destination bucket) | Done |
| Frontend domain-split types | Done |
