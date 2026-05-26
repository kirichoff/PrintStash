"use client";

/**
 * Client-side store for auth tokens (JWT) and the legacy shared API key.
 *
 * Stage 3+ adds JWT login — the web frontend uses Bearer tokens while the
 * OrcaSlicer hook and other scripts continue to use X-API-Key.
 */

const API_KEY_STORAGE = "nexus3d.apiKey";
const TOKEN_STORAGE = "nexus3d.token";
const USER_STORAGE = "nexus3d.user";
const EVENT = "nexus3d:auth-changed";
const UNAUTH_EVENT = "nexus3d:unauthorized";

// ---------------------------------------------------------------------------
// API key (legacy, kept for OrcaSlicer hook compat)
// ---------------------------------------------------------------------------

export function getStoredApiKey(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(API_KEY_STORAGE);
  } catch {
    return null;
  }
}

export function setStoredApiKey(key: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (key && key.trim()) {
      window.localStorage.setItem(API_KEY_STORAGE, key.trim());
    } else {
      window.localStorage.removeItem(API_KEY_STORAGE);
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

// ---------------------------------------------------------------------------
// JWT tokens
// ---------------------------------------------------------------------------

export interface StoredUser {
  id: number;
  username: string;
  email: string | null;
  is_superuser: boolean;
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_STORAGE);
  } catch {
    return null;
  }
}

export function getStoredUser(): StoredUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(USER_STORAGE);
    return raw ? (JSON.parse(raw) as StoredUser) : null;
  } catch {
    return null;
  }
}

export function storeLogin(token: string, user: StoredUser): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(TOKEN_STORAGE, token);
    window.localStorage.setItem(USER_STORAGE, JSON.stringify(user));
    window.dispatchEvent(new Event(EVENT));
  } catch {
    /* ignore */
  }
}

export function clearLogin(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN_STORAGE);
    window.localStorage.removeItem(USER_STORAGE);
    window.dispatchEvent(new Event(EVENT));
  } catch {
    /* ignore */
  }
}

export function isLoggedIn(): boolean {
  return !!getStoredToken();
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

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
