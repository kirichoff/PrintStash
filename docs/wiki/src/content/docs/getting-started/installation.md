---
title: Installation
description: Bring up the Docker Compose stack and create your first admin account.
---

The normal install is Docker Compose. If Docker is already working on the host,
you do not need to install Python, Node, or frontend tooling just to run
PrintStash.

## What you need

- **Docker + Docker Compose** on a `linux/amd64` or `linux/arm64` host (Raspberry
  Pi 4/5, ARM NAS, and Apple-silicon VMs all work; on ARM, STEP/STP files store
  but don't get a 3D preview; see
  [Known limitations](/reference/known-limitations/)).
- **~1 GB RAM minimum, 2 GB comfortable.** Thumbnailing large meshes is the
  heaviest step; give it 2 GB if you upload big STLs.
- **1–2 CPU cores.**
- **Disk:** ~1 GB for the images, plus room for your library. The stored files
  dominate; the SQLite database stays small.

## Quick start

```bash
git clone https://github.com/xiao-villamor/PrintStash.git
cd PrintStash

cp .env.example .env
# Open .env and change VAULT_JWT_SECRET to a long random string.

docker compose up -d
```

The default `docker-compose.yml` **pulls prebuilt images** from GHCR, so there's
no build step. The first `up` downloads a few hundred MB of images; after that it's
instant. When it's done you should have two main containers running,
`printstash-api` and `printstash-frontend`, plus named volumes for the database,
files, thumbnails, and backups.

:::note
The stack starts even without a `.env` (every variable has a default), but the
default `VAULT_JWT_SECRET` is an insecure placeholder. Set your own before the
app is reachable from anything but localhost (see below).
:::

Two variations on the same images:

```bash
# Hardened production: API stays internal, frontend bound to 127.0.0.1 for a
# TLS reverse proxy in front.
docker compose -f docker-compose.prod.yml up -d

# Build from source instead of pulling (contributors):
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

| Service      | URL                                  | What it is                       |
| ------------ | ------------------------------------ | -------------------------------- |
| Web UI       | http://localhost:3000                | The app                          |
| API docs     | http://localhost:8000/docs           | Interactive Swagger reference    |
| Health check | http://localhost:8000/api/v1/health  | Liveness + component readiness   |

The frontend container runs nginx. It serves the built UI and proxies `/api/v1`
and WebSocket traffic to the API, so the browser talks to one origin during a
normal Compose install.

## First launch

Open the UI and you'll be sent to the setup wizard at
`http://localhost:3000/setup`. It walks you through:

1. Creating the **first admin account** (username + password).
2. Choosing a storage backend: `local` disk or S3-compatible.
3. Confirming data directories and backup retention.
4. Optionally wiring up a separate S3/R2 bucket for backups.

There is **no default username or password**. The setup account is the first
account in the database. If the wizard will not complete, check the API logs and
fix that problem; there is no hidden fallback login.

Once you're in, head to **Settings** to mint an API key, then add printers and
start uploading.

## Optional services

The Compose file ships Postgres and MinIO behind profiles, so they stay off
unless you ask for them:

```bash
# Run with Postgres instead of SQLite
docker compose --profile postgres up -d

# Run a local MinIO target for S3-compatible storage testing
docker compose --profile s3 up -d minio
```

Postgres listens on `5432`, and MinIO on `9000` (API) / `9001` (console). You
only need these for larger or multi-user installs; see
[Configuration](/getting-started/configuration/).

## Before you expose it

PrintStash is designed for a **trusted home network** first. Before it is
reachable from outside your LAN, settle these:

- Set a strong, unique `VAULT_JWT_SECRET`. Treat it like a password; anyone who
  has it can forge valid tokens.
- Put it behind a reverse proxy with TLS. Don't port-forward the raw containers.
- Decide on storage. SQLite + local disk is the default and the best-tested path;
  switch to Postgres and/or S3 only if you actually need them.
- Plan backups *before* you need them. See
  [Backup & restore](/guides/backup-and-restore/).

### Reverse proxy with TLS

Use `docker-compose.prod.yml`: it publishes **only** the frontend and binds it to
`127.0.0.1:3000`, so the containers aren't reachable except through your proxy.
The frontend's nginx already proxies `/api/v1` and WebSocket traffic to the API,
so the proxy has a single upstream: forward everything to `127.0.0.1:3000` and
you're done. WebSockets (live printer status) must be allowed through; the
examples below handle that automatically.

**Caddy** (automatic Let's Encrypt TLS), a two-line `Caddyfile`:

```caddyfile
printstash.example.com {
    reverse_proxy 127.0.0.1:3000
}
```

**Traefik** (labels on the frontend service, if you run Traefik in Docker):

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.printstash.rule=Host(`printstash.example.com`)"
  - "traefik.http.routers.printstash.entrypoints=websecure"
  - "traefik.http.routers.printstash.tls.certresolver=le"
  - "traefik.http.services.printstash.loadbalancer.server.port=3000"
```

**nginx:** proxy a server block to the frontend, passing the upgrade headers so
WebSockets work:

```nginx
server {
    server_name printstash.example.com;
    # listen 443 ssl;  # terminate TLS here (certbot, etc.)

    client_max_body_size 512m;  # match VAULT_MAX_UPLOAD_MB

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

If you raise `VAULT_MAX_UPLOAD_MB`, raise the equivalent body-size limit on your
proxy too (Caddy and Traefik don't cap by default; nginx does, via
`client_max_body_size` above).

## Troubleshooting first boot

- **Setup wizard never appears / 502 from the UI.** The API probably hasn't
  finished migrating yet. `docker compose logs -f api` and wait for it to report
  the server is up; migrations run automatically on startup.
- **"Connection refused" on port 3000 or 8000.** Something else is bound to the
  port, or the container failed to start. Check `docker compose ps`.
- **Health check shows a component unhealthy.** Hit
  `http://localhost:8000/api/v1/health` directly; it breaks readiness out by
  database, storage, backup, and printer providers, so the failing component is
  obvious.

For upgrading an existing install, see
[Upgrading](/guides/upgrading/).
