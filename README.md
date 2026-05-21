# Nexus3D Vault

Self-hosted, Plex-style asset management for 3D printing workflows.
Ingest STL / 3MF / G-Code, deduplicate, extract slicer metadata, browse via API and Web UI.

> **Status:** Stage 2 (The Visual Experience) — Next.js 14 frontend with asset grid,
> model detail pages, R3F 3D viewer, and manual upload. Backend ingestion (Stage 1)
> is complete.

See [`AGENTS.md`](./AGENTS.md) for conventions and the
[architecture skill](.opencode/skills/nexus3d-vault/SKILL.md) for the deep dive.

---

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env and set VAULT_API_KEY
docker compose up --build -d
docker compose logs -f api
```

| Service   | URL                     |
| --------- | ----------------------- |
| API       | <http://localhost:8000> |
| Swagger   | <http://localhost:8000/docs> |
| Frontend  | <http://localhost:3000> |

Smoke test:
```bash
curl http://localhost:8000/api/v1/health

curl -F "file=@sample.gcode" \
     -F "model_name=Bracket v1" \
     -F "category=Functional/Brackets" \
     -H "X-API-Key: changeme" \
     http://localhost:8000/api/v1/ingest/orca
```

---

## Local development (no Docker)

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export VAULT_API_KEY=devkey
export VAULT_DB_URL=sqlite:///./dev.sqlite
export VAULT_DATA_DIR=./_data/files
export VAULT_THUMB_DIR=./_data/thumbs

uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install

# In development, the frontend proxies /api/v1/* to the backend.
# If your backend is not on localhost:8000, set:
# export NEXT_PUBLIC_API_URL=http://localhost:8000

npm run dev
```

---

## OrcaSlicer integration

In OrcaSlicer: **Process → Others → Post-processing scripts**:

```
/usr/bin/python3 /absolute/path/to/scripts/nexus3d_orca_push.py \
    --url http://your-vault-host:8000 \
    --api-key YOUR_VAULT_API_KEY \
    --category "Functional/Brackets"
```

The script is stdlib-only and **always exits 0** — a vault outage will never
block your export. Failures are logged to `~/.nexus3d_orca_push.log`.

---

## Endpoints (Stage 1–2)

| Method | Path                           |
| ------ | ------------------------------ |
| GET    | `/api/v1/health`               |
| POST   | `/api/v1/ingest/orca`          |
| GET    | `/api/v1/ingest/jobs/{job_id}` |
| GET    | `/api/v1/models`               |
| GET    | `/api/v1/models/{id}`          |
| DELETE | `/api/v1/models/{id}`          |
| GET    | `/api/v1/files/{id}/download`  |
| GET    | `/api/v1/files/{id}/thumbnail` |

---

## Roadmap

| Stage | Codename              | Status     |
| ----- | --------------------- | ---------- |
| 1     | The Headless Vault    | completed  |
| 2     | The Visual Experience | **active** |
| 3     | The Hub               | planned    |
| 4     | Cloud Readiness       | planned    |

---

## License

TBD.
