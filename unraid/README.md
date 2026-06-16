# PrintStash on Unraid

PrintStash is two containers: **PrintStash-API** (backend) and **PrintStash-Frontend**
(web UI / nginx). The frontend proxies `/api/v1` to the API at the hostname `api`, so
both containers must share a **user-defined Docker network** that does name resolution
(Unraid's default `bridge` does not).

## Option A: Community Applications templates (this folder)

1. **Create the network** (one time). On the Unraid terminal:
   ```
   docker network create printstash
   ```
2. **Install PrintStash-API** from the template:
   - Network: `printstash`
   - Set a strong **JWT secret** (`openssl rand -hex 32`).
   - The template already runs DB migrations on start and sets the network alias `api`.
3. **Install PrintStash-Frontend** from the template:
   - Network: `printstash`
   - Keep the WebUI port (default `3000`).
4. Open `http://<server-ip>:3000` and complete the first-run setup wizard.

> Both containers must stay on the `printstash` network. If the frontend shows
> "connection refused" for `/api/v1`, the API isn't reachable as `api` on that network.

## Option B: Docker Compose Manager plugin (recommended, simpler)

PrintStash ships an official `docker-compose.yml`. If you have the **Compose Manager**
plugin (from Community Applications), this is the smoother path because the compose file
already wires the two services, the network, volumes, and the migration command:

1. Install the *Docker Compose Manager* plugin.
2. Add a new stack and paste the contents of the repo's
   [`docker-compose.yml`](https://github.com/xiao-villamor/PrintStash/blob/main/docker-compose.yml).
3. Set `VAULT_JWT_SECRET` (and adjust volume paths to `/mnt/user/appdata/printstash/...`).
4. Compose up, then open `http://<server-ip>:3000`.

## Submitting to Community Applications

Per https://ca.unraid.net/submit/help, CA indexes templates from a public GitHub repo:

1. Host these XML files in a public repo (this `unraid/` folder works, or a dedicated
   `unraid-templates` repo).
2. Make sure each template's `<TemplateURL>` points at its own **raw** GitHub URL.
3. Submit the repository on the CA submit page and follow the moderation steps.

### Notes / nice-to-haves for a cleaner CA experience
- Provide a square **PNG** icon (CA prefers PNG over SVG) and point `<Icon>` at it.
- Consider baking `alembic upgrade head` into the API image's entrypoint so the default
  command "just works" without the Post Arguments override.
- Consider making the frontend's API target configurable (env) so a custom network isn't
  strictly required.
