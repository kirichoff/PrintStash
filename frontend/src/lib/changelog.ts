// ─────────────────────────────────────────────────────────────────────────
// SINGLE SOURCE OF TRUTH for the app changelog + repo identity.
//
// Keep this updated on every release / notable user-facing change, then bump
// the version in: backend/pyproject.toml, backend/app/core/config.py
// (app_version), and frontend/package.json. The Settings → About tab renders
// CHANGELOG[0] as the current version's details.
//
// Newest release goes FIRST. CHANGELOG[0].version MUST equal the version in
// frontend/package.json — this is enforced by changelog.test.ts, so a forgotten
// entry fails CI instead of silently leaving the About tab on an old release.
// ─────────────────────────────────────────────────────────────────────────

export const GITHUB_REPO = "xiao-villamor/PrintStash";

export interface ChangelogEntry {
  version: string;
  date: string; // human-readable, e.g. "Jun 2026"
  changes: string[];
}

export const CHANGELOG: ChangelogEntry[] = [
  {
    version: "0.6.1",
    date: "Jun 2026",
    changes: [
      "Import from URL now accepts Printables, MakerWorld, and Thingiverse model pages — paste the page you're on, no need to find the direct download link",
      "Fixed the About tab showing the previous release instead of the current one",
      "Fixed 3D model previews taking 20-30s to load — STL files now serve near-instantly",
    ],
  },
  {
    version: "0.6.0",
    date: "Jun 2026",
    changes: [
      "External libraries: mirror a NAS or local folder in place — files are indexed where they live, never copied",
      "Two-way sync: scans pick up added, removed, and edited files; web uploads and revisions write back into the folder",
      "Folder structure maps to collections (mirror mode), or route everything into one collection (single mode)",
      "Your files are never overwritten or deleted — trash and cleanup skip externally-linked files, and uploads never clobber existing ones",
      "Unmount-safe: a scan aborts instead of mass-deleting when the folder is missing or unexpectedly empty",
      "Fixed scheduled scans silently stopping after a library's first scan",
    ],
  },
  {
    version: "0.5.0",
    date: "Jun 2026",
    changes: [
      "Import models from a URL or a .zip archive, with selective per-file extraction",
      "STEP / STP CAD files: ingest, 3D preview, and thumbnails",
      "Public share links — expiring, read-only, view-only by default (optional download)",
      "Measured filament + print duration captured from the printer, with real per-print cost",
      "Auto-mark a revision known-good after its first successful print (toggle in Design settings)",
      "Delete G-code revisions from a model's Revisions tab",
      "Log print history against an ad-hoc printer name — no registered printer required",
      "Moonraker printer inventory now stays in sync, removes files deleted elsewhere, and supports deleting printer files",
      "Printer detail UI refreshed with Moonraker / Klipper config, diagnostics, and profile/settings-aligned styling",
    ],
  },
  {
    version: "0.4.0",
    date: "Jun 2026",
    changes: [
      "Frontend rebuilt on Vite + React Router (migrated off Next.js)",
      "TanStack Query caching: shared collections/tags cache, refetch on window focus, auto-refresh after edits",
      "Fixes the model detail page error and broken 3D preview / downloads under multi-user access",
      "Served by nginx with a same-origin API + WebSocket proxy",
    ],
  },
  {
    version: "0.3.0",
    date: "Jun 2026",
    changes: [
      "Multi-user access: collection-level roles (view / edit / admin) per user",
      "Admin user management and access controls",
      "Authenticated assets: thumbnails, 3D previews, and downloads now require sign-in",
      "Lossless WebP thumbnails",
      "Settings refinements and collections sidebar fixes",
    ],
  },
  {
    version: "0.2.0",
    date: "Jun 2026",
    changes: [
      "Profiles: inline auto-save editing, aligned columns",
      "Outliner: fixed subfolder expansion in the collections sidebar",
      "Settings: new About tab with version history",
      "Theme-aware browser favicon (light/dark)",
      "Catalog: tags are now removable",
      "UI/UX polish across model detail, grid, and filters",
    ],
  },
  {
    version: "0.1.0",
    date: "Initial release",
    changes: [
      "Self-hosted vault for STL/3MF/G-code assets",
      "Collections, tags, and drag-and-drop organization",
      "Moonraker/Klipper printer control (Bambu LAN beta)",
      "Filament & printer presets with cost tracking",
    ],
  },
];

/** Current app version = newest changelog entry. */
export const APP_VERSION = CHANGELOG[0].version;
