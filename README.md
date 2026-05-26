# Nexus3D Vault

A self-hosted asset library for your 3D prints. Drop STLs, 3MFs, and
G-code files into it. The vault keeps them organized, de-duplicated,
and searchable — with a web UI that shows you what you've got and a
3D viewer so you don't have to guess from filenames.

It's built to work with OrcaSlicer. Every time you slice something
and hit "Export G-code", the vault picks it up, extracts the settings
you used (filament type, layer height, print time...), and files it
away. Six months later when you need to reprint that bracket, you
know exactly which file it was and what settings you sliced it with.

## What it looks like

Still early. The web UI has an asset grid, model detail pages, and a
3MF/STL viewer. Search and filtering work. Printer monitoring (Stage 3)
is in progress.

## Quick start

```bash
cp .env.example .env
# open .env, pick an API key, set a real JWT secret
docker compose up --build -d
```

Then open your browser:

| Service  | URL                          |
| -------- | ---------------------------- |
| Web UI   | <http://localhost:3000>      |
| API docs | <http://localhost:8000/docs> |
| Health   | <http://localhost:8000/api/v1/health> |

First login: `admin` / `admin`. Change it from the `.env` or the UI.

### Send it a file to test

```bash
curl -F "file=@some_print.gcode" \
     -F "model_name=Desk Bracket" \
     -F "category=Functional/Brackets" \
     -H "X-API-Key: changeme" \
     http://localhost:8000/api/v1/ingest/orca
```

This is the same endpoint your OrcaSlicer hook will call.

## Hook it up to OrcaSlicer

In OrcaSlicer, go to **Process → Others → Post-processing scripts** and
paste something like:

```
/usr/bin/python3 /path/to/nexus3d-vault/scripts/nexus3d_orca_push.py \
    --url http://your-server:8000 \
    --api-key YOUR_API_KEY \
    --category "Functional/Brackets"
```

The script is stdlib-only (no pip install needed) and it will never block
your export if the vault is down — it logs failures and exits clean.

## What it does with your files

When you send a G-code file:

1. Hashes it (SHA-256) so duplicates don't create extra copies
2. Pulls out slicer settings from the header comments (OrcaSlicer and
   PrusaSlicer both embed these)
3. Extracts the embedded preview thumbnail if there is one
4. Files the G-code under a model slug with version tracking — so if you
   slice the same model again with different settings, it keeps both

When you send an STL or 3MF:

1. Same deduplication
2. Runs it through Trimesh to pull bounding box, volume, triangle count
3. Renders a thumbnail (software rasteriser, no GPU needed)
4. Lets you download a normalized STL from the UI viewer

Tags and categories are supported if you pass `--tags` and `--category`
from the hook. You can also edit them from the web UI.

## Architecture

```
Browser ──► Next.js (port 3000) ──► FastAPI (port 8000) ──► SQLite
                                        │
                                   OrcaSlicer hook
                                   (POST /api/v1/ingest/orca)
```

Both the frontend and API live in Docker by default. The API writes files
to named Docker volumes so your data sticks around.

For local development the frontend and backend can run natively
(see [Development](#development) below).

The backend has an optional Rust acceleration module that speeds up
thumbnail rendering (rayon-parallel rasteriser) and G-code scanning
(single-pass SHA-256 + parse + thumbnail extract). If you don't have
a Rust toolchain, it falls back to pure Python and works exactly the
same — just a bit slower on really big meshes.

## Development

You'll need Python 3.11+ and Node.js 20+.

### Backend

```bash
cd backend
uv sync

VAULT_API_KEY=devkey \
VAULT_DB_URL=sqlite:///./dev.sqlite \
VAULT_DATA_DIR=./_data/files \
VAULT_THUMB_DIR=./_data/thumbs \
uv run uvicorn app.main:app --reload
```

If you don't have uv, create a venv and pip install from pyproject.toml.

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

The dev server proxies `/api` to `http://localhost:8000` automatically.

### Running tests

```bash
cd backend
uv run pytest tests
```

## How far along is it

| Stage | What it covers                           | Status    |
| ----- | ---------------------------------------- | --------- |
| 1     | API, ingestion, dedup, G-code parsing    | done      |
| 2     | Web UI, asset grid, R3F viewer, search   | done      |
| 3     | Moonraker/Klipper printer farm           | in progress |
| 4     | Multi-user auth, Postgres, S3            | planned   |

Stage 3 is the current focus — bidirectional communication with Klipper
so you can browse the vault, pick a file, and send it straight to a printer.

## What it is not

- Not a slicer. It doesn't generate G-code. You bring your own sliced files.
- Not a cloud service. It runs on your own hardware by design. Cloud stuff
  (if it ever happens) will be opt-in.
- Not a print queue manager. You can send jobs to Moonraker from the UI,
  but the actual queue management lives on your printer firmware.

## License

AGPL-3.0.

I picked AGPL because this is a tool for makers. If you improve it, share
back. If you're just running it on your own server to manage your own
prints, the license doesn't get in your way.
