# Nexus3D Vault — Backend

FastAPI backend for the vault. Ingests STL / 3MF / G-code, extracts
metadata, deduplicates by hash, and serves everything through a versioned
REST API. Used by the Next.js frontend and the OrcaSlicer post-processing
hook.

See the [root README](../README.md) for the big picture.

## Stack

- Python 3.11+, FastAPI, SQLModel, Uvicorn
- SQLite (Postgres comes in Stage 4)
- Trimesh for mesh geometry and STL export
- Optional Rust acceleration module (rayon-parallel thumbnail rendering,
  single-pass G-code scanner)

## Quick start (development)

```bash
cd backend

# First time — create venv and install deps
uv sync

# Run the server
VAULT_DB_URL=sqlite:///./dev.sqlite \
VAULT_DATA_DIR=./_data/files \
VAULT_THUMB_DIR=./_data/thumbs \
VAULT_API_KEY=devkey \
uv run uvicorn app.main:app --reload
```

Open <http://localhost:8000/docs> for the Swagger UI.

## Layout

```
backend/
├── pyproject.toml
├── Dockerfile
├── rust/                  ← optional native acceleration (Rust + PyO3)
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs         ← PyO3 bindings: gcode_scan, rasterise
│       ├── gcode.rs       ← combined sha256 + metadata + thumbnail
│       └── raster.rs      ← parallel triangle rasteriser
└── app/
    ├── main.py            ← FastAPI app, lifespan, Starlette
    ├── core/              ← config, security, logging, time, http helpers
    ├── db/                ← SQLModel tables, session, DB init
    ├── schemas/           ← Pydantic DTOs
    ├── services/          ← business logic
    └── api/v1/            ← routers (files, ingest, models, printers, taxonomy, auth)
```

## Environment variables

| Variable | What it does | Example |
|---|---|---|
| `VAULT_DB_URL` | Database connection string | `sqlite:///./dev.sqlite` |
| `VAULT_DATA_DIR` | Where ingested files live | `./_data/files` |
| `VAULT_THUMB_DIR` | Where rendered thumbnails go | `./_data/thumbs` |
| `VAULT_API_KEY` | Shared key for write endpoints | `devkey` |
| `VAULT_JWT_SECRET` | Signing key for auth tokens | anything random |
| `VAULT_JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `VAULT_ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime | `60` |
| `VAULT_MAX_UPLOAD_MB` | Upload size limit | `512` |
| `VAULT_LOG_LEVEL` | Python log level | `INFO` |

> The first admin user is created via the web-based first-run wizard at
> `/setup` — there is no env-driven default account. Storage paths above are
> the defaults; the wizard can override `data_dir` / `thumb_dir` per install
> and persists them in the `system_config` table.

## Building the Rust module

The backend works fine without it (everything falls back to pure Python).
If you want the speed boost for large meshes and G-code:

```bash
# one-time setup
sudo apt install build-essential python3-dev
pip install maturin

cd backend/rust
maturin build --release
pip install target/wheels/nexus3d_rust-*.whl
```

The Python wrappers in `app/services/gcode_rust.py` and
`app/services/raster_rust.py` detect the module at import time. If it's
there, the fast path activates automatically. If it's not, the pure-Python
code runs as usual.

This is all handled at build time in the Docker image (see the
`rust-builder` stage in the Dockerfile).

## Docker

From the repo root:

```bash
docker compose up --build
```

The compose file mounts named volumes under `/data/` so your files and DB
survive container rebuilds.

## Tests

```bash
uv run pytest tests
```

Tests use `tmp_path` — they never touch the real data volume.
