# Stage 2 — The Visual Experience (execution log)

This document tracks every meaningful change made during Stage 2 development.

---

## Goals

- Next.js 14 frontend with App Router, Tailwind CSS, and Shadcn/ui design system.
- Asset grid with thumbnail previews, search, and category badges.
- Model detail page with full metadata, file list with downloads, and print profile card.
- React Three Fiber 3D STL viewer embedded in model detail pages.
- Manual upload page with drag-and-drop, form fields, and API key input.
- Docker Compose integration for the frontend service.
- CORS enabled on the backend for direct browser-to-API communication.

---

## Build Log

### 2026-05-11 — Stage 2 scaffolding
- Created `frontend/` directory with Next.js 14 config:
  - `package.json` — deps: next, react, three, @react-three/fiber, @react-three/drei, tailwind, shadcn/ui primitives.
  - `tsconfig.json` — strict, path aliases `@/*`.
  - `next.config.js` — standalone output, API rewrite proxy to backend.
  - `tailwind.config.ts` — full Shadcn CSS variable theme.
  - `postcss.config.js` — tailwind + autoprefixer.
  - `components.json` — Shadcn/ui manifest.
  - `Dockerfile` — multi-stage Node 20 Alpine build with standalone output.
- Created Shadcn/ui base components manually (no CLI available in sandbox):
  - `button`, `card`, `input`, `badge`, `separator`, `skeleton`.
- Created `frontend/src/lib/utils.ts` — `cn()` with clsx + tailwind-merge.
- Created `frontend/src/types/index.ts` — TypeScript interfaces mirroring backend DTOs.
- Created `frontend/src/lib/api.ts` — typed fetch layer with error handling.

### 2026-05-11 — Pages & components
- `frontend/src/app/layout.tsx` — Root layout with Inter font, Header nav.
- `frontend/src/app/page.tsx` — Asset grid (Server Component), fetches models, streams `ModelGrid`.
- `frontend/src/app/models/[id]/page.tsx` — Model detail (Server Component), fetches single model.
- `frontend/src/app/upload/page.tsx` — Upload page wrapping `UploadForm`.
- `frontend/src/components/header.tsx` — Sticky nav with logo, Assets, Upload links.
- `frontend/src/components/model-card.tsx` — Card with thumbnail, name, category/tags, file count.
- `frontend/src/components/model-grid.tsx` — Search filter + responsive grid (1/2/3/4 cols).
- `frontend/src/components/model-detail.tsx` — Two-column layout:
  - Left: thumbnail card + R3F STL viewer (if STL file exists).
  - Right: print profile metadata card + file list with download buttons.
  - Delete action with API key prompt.
- `frontend/src/components/stl-viewer.tsx` — R3F Canvas with STLLoader, auto-centering, orbit controls, lighting.
- `frontend/src/components/upload-form.tsx` — Drag-and-drop zone, file input, name/category/tags fields, API key, progress state, job confirmation.

### 2026-05-11 — Backend & infra updates
- Added `CORSMiddleware` to `backend/app/main.py` (allow_origins=["*"]) so the browser can talk to the API directly.
- Updated `docker-compose.yml` to add `frontend` service (build from `./frontend`, port 3000, depends_on api healthcheck). Removed obsolete `version` attribute.
- Updated `frontend/next.config.js` to set `output: "standalone"` for the Docker multi-stage build.
- Fixed `frontend/Dockerfile`:
  - `npm ci` → `npm install` (no lockfile committed yet).
  - `COPY .` → `COPY . .` (Dockerfile syntax).
  - Added `ARG NEXT_PUBLIC_API_URL=http://api:8000` in builder stage so rewrites resolve to the API container internally.
- Added `getAssetUrl()` in `frontend/src/lib/api.ts` to produce correct absolute/relative URLs depending on server vs browser context.
- Replaced Next.js `<Image>` with standard `<img>` for API thumbnails to avoid Image optimization conflicts with rewrite proxies.

---

## Known Issues / Resolved

- **R3F STLLoader import path** — uses `three/examples/jsm/loaders/STLLoader`. In some three.js versions this path may shift; the component is wrapped in `"use client"` to avoid SSR issues.
- **Thumbnail paths** — `_thumb_url()` on the backend returns relative paths like `/api/v1/files/{id}/thumbnail`. The frontend uses `getAssetUrl()` to resolve them correctly in both browser (via rewrite) and server-side (direct internal) contexts.
- **Image optimization** — Switched from Next.js `<Image>` to standard `<img>` for API-served thumbnails to avoid Image optimization complexity with dynamic/rewritten URLs. Next.js `<Image>` remains available for static assets in `public/`.

---

## Deferred to Later Stages

- **Stage 3:** Moonraker bridge, printer state dashboard, send-to-print actions.
- **Stage 4:** OAuth2 login UI, user profiles, RBAC-gated delete/upload buttons.
