// Remembers the last vault collection (folder) the user was browsing so the
// PrintStash logo and post-delete navigation return there instead of resetting
// to "All Models". Collection selection lives in the URL as `?c=<path>`, but
// that param is dropped when the user navigates to Settings, a model, etc. —
// persisting it here lets us restore the context on the way back.
export const LAST_COLLECTION_STORAGE_KEY = "printstash.last.collection";
export const LAST_VIEW_STORAGE_KEY = "printstash.last.view";

/** Persist the current collection path (or clear it at the root). Best-effort. */
export function rememberLastCollection(path: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (path) window.localStorage.setItem(LAST_COLLECTION_STORAGE_KEY, path);
    else window.localStorage.removeItem(LAST_COLLECTION_STORAGE_KEY);
  } catch {
    // Storage unavailable (private mode / disabled) — context restore is a
    // nicety, not a requirement, so silently skip it.
  }
}

/** Read the remembered collection path, or null if none/unavailable. */
export function readLastCollection(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(LAST_COLLECTION_STORAGE_KEY) || null;
  } catch {
    return null;
  }
}

/** Persist the last vault tab (Models vs Documents) the user was viewing. */
export function rememberLastView(view: "models" | "docs"): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LAST_VIEW_STORAGE_KEY, view);
  } catch {
    // Best-effort, see rememberLastCollection.
  }
}

/** Read the remembered vault tab, defaulting to Models. */
export function readLastView(): "models" | "docs" {
  if (typeof window === "undefined") return "models";
  try {
    return window.localStorage.getItem(LAST_VIEW_STORAGE_KEY) === "docs" ? "docs" : "models";
  } catch {
    return "models";
  }
}

/** Home URL that restores the last collection + tab, e.g. `/?c=spoolers&v=docs`. */
export function lastVaultHref(): string {
  // Build by hand (not URLSearchParams) so spaces encode as %20, matching how
  // the rest of the app writes `?c=` — URLSearchParams would emit `+`.
  const parts: string[] = [];
  const path = readLastCollection();
  if (path) parts.push(`c=${encodeURIComponent(path)}`);
  if (readLastView() === "docs") parts.push("v=docs");
  return parts.length ? `/?${parts.join("&")}` : "/";
}
