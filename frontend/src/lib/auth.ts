"use client";

/**
 * Simple client-side store for the vault's shared API key.
 *
 * Stage 1–3 of Nexus3D ships with a single `VAULT_API_KEY` shared across all
 * users. Asking the user to paste it on every write is brutal UX, so we cache
 * it in localStorage and let api.ts attach it transparently.
 *
 * Stage 4 will replace this with real OAuth/JWT and this module will go away.
 */

const STORAGE_KEY = "nexus3d.apiKey";
const EVENT = "nexus3d:auth-changed";

export function getStoredApiKey(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredApiKey(key: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (key && key.trim()) {
      window.localStorage.setItem(STORAGE_KEY, key.trim());
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
    window.dispatchEvent(new Event(EVENT));
  } catch {
    /* ignore */
  }
}

export function clearStoredApiKey(): void {
  setStoredApiKey(null);
}

export function hasStoredApiKey(): boolean {
  return !!getStoredApiKey();
}

/** Subscribe to in-tab changes. Returns an unsubscriber. */
export function onAuthChange(cb: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const handler = () => cb();
  window.addEventListener(EVENT, handler);
  window.addEventListener("storage", handler);
  return () => {
    window.removeEventListener(EVENT, handler);
    window.removeEventListener("storage", handler);
  };
}

/** Lightweight 401 broadcast so banners can react. */
const UNAUTH_EVENT = "nexus3d:unauthorized";
export function emitUnauthorized(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(UNAUTH_EVENT));
}
export function onUnauthorized(cb: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const handler = () => cb();
  window.addEventListener(UNAUTH_EVENT, handler);
  return () => window.removeEventListener(UNAUTH_EVENT, handler);
}
