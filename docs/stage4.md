# Stage 4 — Cloud Readiness

**Codename:** Cloud Readiness
**Status:** active (just started)

## Goal

Productionize the vault for multi-user, multi-tenant deployments. Migrate from
SQLite to Postgres with Alembic migrations, harden authentication with proper
OAuth2/JWT flows, add multi-tenant isolation, implement audit logging, and polish
S3 storage for production use.

---

## Execution Log

### Phase 4a — Postgres + Alembic (foundation)

- [ ] Add Postgres drivers (`asyncpg`, `psycopg2`) to `pyproject.toml`
- [ ] Set up Alembic (`alembic init`, autogenerate initial migration from SQLModel metadata)
- [ ] Implement `async_session()` on `SessionFactory` Protocol (replacing `NotImplementedError`)
- [ ] Create `create_async_engine()` in `db/session.py` with connection pool config
- [ ] Convert FastAPI `get_session()` to async generator with `AsyncSession`
- [ ] Add Postgres service to `docker-compose.yml`
- [ ] Write one-off SQLite→Postgres data migration script
- [ ] Update README with Postgres configuration instructions

### Phase 4b — OAuth2/JWT hardening

- [x] Refactor frontend API client into domain modules behind a stable `@/lib/api` barrel
- [ ] Add `RefreshToken` model (token hash, user_id, expires_at, revoked)
- [ ] Implement `POST /auth/refresh` and `POST /auth/logout` endpoints
- [ ] Replace raw `Header` auth with FastAPI's `OAuth2PasswordBearer`
- [ ] Add role-based access: enforce `is_superuser` on admin endpoints
- [ ] Add `scope` to JWT payload (read/write/admin)
- [ ] Implement in-memory token blocklist (invalidated on logout)

### Phase 4c — Hard-delete + GC

- [ ] Add `deleted_at` column to File, Printer, PrintJob, User, Tag, Category
- [ ] Add `deleted_by` FK to User on all soft-deletable tables
- [ ] Implement `DELETE` endpoints for printers, categories, tags, users (soft)
- [ ] Implement `POST /{resource}/{id}/restore` endpoints
- [ ] Implement hard-delete endpoint: `DELETE /admin/{resource}/{id}?hard=true`
- [ ] Implement scheduled GC background task (purge rows with `deleted_at < retention`)
- [ ] Implement orphan file cleanup (delete blobs when DB records are purged)

### Phase 4d — Audit logs

- [ ] Add `AuditLog` model (actor_id, action, resource_type, resource_id, diff JSON, ip, timestamp)
- [ ] Add `created_by` / `updated_by` columns to Model, Printer, PrintJob, Category, Tag
- [ ] Implement SQLAlchemy event listener for auto-audit on writes
- [ ] Implement `GET /api/v1/admin/audit` endpoint (admin-only, filterable)
- [ ] Add audit log pagination and filtering by resource/resource_id

### Phase 4e — Multi-tenant

- [ ] Add `Organization` model (id, name, slug, plan, is_active)
- [ ] Add `user_organizations` link table (user_id, organization_id, role)
- [ ] Add `organization_id` FK to Model, File, Printer, PrintJob, Category, Tag, User
- [ ] Implement SQLAlchemy event to auto-filter queries by `current_organization_id()`
- [ ] Add `org_id` to JWT payload; extract in auth dependency
- [ ] Migrate existing single-tenant data to a default "Default" Organization
- [ ] Implement `POST /api/v1/orgs` (org creation + owner assignment)
- [ ] Add S3 key namespace: `vault-data/{org_slug}/files/...`
- [ ] Frontend: `<WorkspaceSelector>` component in topbar
- [ ] Frontend: `[org_slug]/` route prefix for tenant-scoped views

### Phase 4f — S3 production hardening

- [ ] Implement multipart upload for files > 50MB in `S3StorageBackend`
- [ ] Implement pre-signed URL generation for direct downloads
- [ ] Add MinIO service to `docker-compose.yml` for local dev/test
- [ ] Add S3 health check probe to `/api/v1/health`
- [ ] Implement bucket lifecycle policy configuration (expiration, tiering)

---

## Pre-existing Stage 4 infrastructure (carried from Stage 1-3)

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
