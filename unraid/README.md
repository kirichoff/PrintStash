# PrintStash on Unraid

PrintStash runs as **two containers**:

| Container | Role | Port |
|-----------|------|------|
| **PrintStash-API** | Backend API + database | 8000 |
| **PrintStash-Frontend** | Web UI you open in the browser (nginx) | 3000 |

The frontend serves the app and proxies `/api/v1` (including WebSockets) to the
backend at the hostname **`api`**. Because of that, **both containers must share
a user-defined Docker network** that does name resolution — Unraid's built-in
`bridge` network does **not**, so the names won't resolve there.

---

## Install (Community Applications templates)

### 1. Create the network (one time)

On the Unraid terminal (or **Settings → Docker → add network**):

```bash
docker network create printstash
```

### 2. Install PrintStash-API **first**

From the `printstash-api` template:

- **Network:** `printstash`
- **JWT secret** (required): generate a long random string, e.g.
  ```bash
  openssl rand -hex 32
  ```
- Leave the volume paths at their defaults (`/mnt/user/appdata/printstash/...`)
  or point them wherever you keep app data.

The template already:
- relies on the API image, which runs database migrations on every start
  (`alembic upgrade head`) from its entrypoint — no command override needed, and
- gives the container the network alias **`api`** so the frontend can reach it.

> Install the API **before** the frontend — the frontend expects `api` to
> already be resolvable on the `printstash` network.

### 3. Install PrintStash-Frontend

From the `printstash-frontend` template:

- **Network:** `printstash`
- Keep the **WebUI port** (default `3000`).
- If you raise the API's max upload size, match `NGINX_CLIENT_MAX_BODY_SIZE`
  here (e.g. `512m`).

### 4. Open the app and finish setup

Browse to `http://<server-ip>:3000` and complete the **first-run setup wizard**:

- create your admin account,
- choose **storage** — local disk (default) **or S3/R2** (bucket, endpoint, and
  keys are entered here in the wizard — *not* as container variables), and
- optionally configure **backups** (local and/or an S3 destination).

That's it — you're in your vault.

---

## Alternative: Docker Compose Manager plugin

PrintStash ships an official `docker-compose.yml` that already wires both
services, the network, volumes, and the migration command. If you have the
**Compose Manager** plugin (from Community Applications), this is the simplest
path:

1. Install the *Docker Compose Manager* plugin.
2. Add a new stack and paste the repo's
   [`docker-compose.yml`](https://github.com/xiao-villamor/PrintStash/blob/main/docker-compose.yml).
3. Set `VAULT_JWT_SECRET` and adjust volume paths to
   `/mnt/user/appdata/printstash/...` if you like.
4. Compose up, then open `http://<server-ip>:3000`.

---

## Configuration reference

Most settings are configured **in the app's setup wizard / Settings** and stored
in the database — including storage backend (local vs S3/R2) and backups. The
container variables are mainly bootstrap defaults:

| Variable | Container | Required | Notes |
|----------|-----------|----------|-------|
| `VAULT_JWT_SECRET` | API | ✅ | Signs auth tokens. Use `openssl rand -hex 32`. |
| `VAULT_MAX_UPLOAD_MB` | API | – | Max upload size in MB (default `512`). |
| `NGINX_CLIENT_MAX_BODY_SIZE` | Frontend | – | Keep in sync with the above, e.g. `512m`. |
| `VAULT_BACKUP_RETENTION_DAYS` | API | – | `0` keeps backups forever. |
| `VAULT_ACCESS_TOKEN_EXPIRE_MINUTES` | API | – | JWT lifetime (default `60`). |
| `VAULT_LOG_LEVEL` | API | – | `DEBUG` / `INFO` / `WARNING` / `ERROR`. |
| `VAULT_METRICS_TOKEN` | API | – | If set, requires a bearer token to scrape `/metrics` (Prometheus). Leave empty to keep it open on your LAN. |

### Persistent paths (API container)

| Path | Holds |
|------|-------|
| `/data/files` | Uploaded models and G-code |
| `/data/thumbs` | Generated thumbnails |
| `/data/db` | SQLite database |
| `/data/staging` | Temporary upload/import staging |
| `/data/backups` | Local backup archives |

---

## Troubleshooting

- **Frontend shows "connection refused" / 502 for `/api/v1`** — the API isn't
  reachable as `api` on the `printstash` network. Check that **both** containers
  are on the `printstash` network and that the API container has the
  `--network-alias api` extra parameter (the template sets this).
- **Stuck on a blank page or the network's default `bridge`** — recreate the
  containers on the user-defined `printstash` network; the default `bridge` has
  no DNS, so `api` can't resolve.
- **No login works on a fresh install** — there is no default admin account.
  Complete the first-run setup wizard to create one. If setup can't complete,
  fix setup (storage paths, JWT secret) rather than looking for built-in
  credentials.
- **Monitoring** — the API exposes Prometheus metrics at
  `http://<server-ip>:8000/metrics` for Grafana/Prometheus dashboards.

---

## For maintainers: submitting to Community Applications

CA indexes templates from a public GitHub repo. The required layout (per the
[official starter repo](https://github.com/unraid/unraid-community-apps-starter))
lives at the repository root:

```
ca_profile.xml                      # repository overview + support metadata (required)
icon.svg                            # repository icon
LICENSE                             # source-available license (Elastic License 2.0)
README.md                           # repository readme
templates/
  printstash-api.xml                # PrintStash-API Docker template
  printstash-frontend.xml           # PrintStash-Frontend Docker template
```

Checklist before submitting on the CA submit page:

1. Repo is **public and active**, with a source-available `LICENSE` (we ship
   Elastic License 2.0). Confirm the current Community Applications policy
   accepts this license before submitting.
2. `ca_profile.xml` has a non-empty `<Profile>` section.
3. Each template lives under `templates/`, has a `<Repository>` tag, and its
   `<TemplateURL>` points at its own **raw** GitHub URL on `main`.
4. Verify every raw URL resolves once merged to `main`
   (`curl -I <raw-url>` → `200`): the two `templates/*.xml`, `icon.svg`, and the
   `<ReadMe>`/`<Icon>` targets.

Nice-to-have: provide a square **PNG** icon (CA prefers PNG over SVG). Migrations
are now baked into the API image entrypoint (they run on every start, before the
server), so the default command works without any Post Arguments override.
