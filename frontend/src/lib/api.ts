import { emitUnauthorized, getStoredApiKey, getStoredToken } from "@/lib/auth";
import {
  CategoryCreate,
  CategoryRead,
  IngestJobStatus,
  IngestResponse,
  ListModelsParams,
  TokenResponse,
  LoginRequest,
  ModelListItem,
  ModelRead,
  ModelUpdate,
  PrintJobRead,
  PrinterCreate,
  PrinterRead,
  PrinterStatusResponse,
  PrinterUpdate,
  SendToPrinter,
  TagCreate,
  TagRead,
  UserRead,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "";

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

function browserBase(): string {
  if (!API_BASE) return "";
  if (API_BASE.includes("://api:")) return "";
  return API_BASE;
}

function serverBase(): string {
  return API_BASE || "http://localhost:8000";
}

function activeBase(): string {
  return isBrowser() ? browserBase() : serverBase();
}

function getUrl(path: string): string {
  const base = activeBase();
  if (base) {
    return `${base.replace(/\/$/, "")}${path}`;
  }
  return path;
}

/**
 * Returns an absolute URL suitable for <img src> or <a href download>.
 * In the browser this uses the public-facing API endpoint (via rewrite or direct).
 */
export function getAssetUrl(path: string): string {
  return getUrl(path);
}

/**
 * Returns a WebSocket URL for the given backend path.
 * Prefers NEXT_PUBLIC_WS_URL, then falls back to the API base or page origin
 * (Next.js rewrites do not proxy WS, so a direct origin is required).
 */
export function getWsUrl(path: string): string {
  if (!isBrowser()) {
    const base = (WS_BASE || API_BASE || "http://localhost:8000").replace(
      /\/$/,
      "",
    );
    return base.replace(/^http/, "ws") + path;
  }
  if (WS_BASE) {
    return WS_BASE.replace(/\/$/, "") + path;
  }
  if (API_BASE && !API_BASE.includes("://api:")) {
    return API_BASE.replace(/\/$/, "").replace(/^http/, "ws") + path;
  }
  // Fall back to same-origin (assumes a reverse proxy in front of both).
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${path}`;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    if (res.status === 401) emitUnauthorized();
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

function authHeaders(apiKey?: string): Record<string, string> {
  const headers: Record<string, string> = {};
  const token = getStoredToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const k = apiKey !== undefined ? (apiKey || undefined) : (getStoredApiKey() ?? undefined);
  if (k) {
    headers["X-API-Key"] = k;
  }
  return headers;
}

function writeHeaders(apiKey?: string): Record<string, string> {
  return authHeaders(apiKey);
}

function jsonHeaders(apiKey?: string): Record<string, string> {
  return { "Content-Type": "application/json", ...authHeaders(apiKey) };
}

/**
 * Bare fetch wrapper for endpoints that don't return JSON (DELETE, POST control).
 * Broadcasts 401s so the auth banner can surface.
 */
async function expectOk(res: Response): Promise<void> {
  if (!res.ok) {
    if (res.status === 401) emitUnauthorized();
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
}

// -- Models ---------------------------------------------------------------

export async function listModels(
  params?: ListModelsParams,
): Promise<ModelListItem[]> {
  const search = new URLSearchParams();
  if (params?.category) search.set("category", params.category);
  if (params?.q) search.set("q", params.q);
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.offset) search.set("offset", String(params.offset));
  if (params?.tag) {
    for (const t of params.tag) search.append("tag", t);
  }
  const qs = search.toString();
  const res = await fetch(getUrl(`/api/v1/models${qs ? `?${qs}` : ""}`), {
    cache: "no-store",
  });
  return handleResponse<ModelListItem[]>(res);
}

export async function getModel(id: number): Promise<ModelRead> {
  const res = await fetch(getUrl(`/api/v1/models/${id}`), {
    cache: "no-store",
  });
  return handleResponse<ModelRead>(res);
}

export async function updateModel(
  id: number,
  payload: ModelUpdate,
  apiKey?: string,
): Promise<ModelRead> {
  const res = await fetch(getUrl(`/api/v1/models/${id}`), {
    method: "PATCH",
    headers: jsonHeaders(apiKey),
    body: JSON.stringify(payload),
  });
  return handleResponse<ModelRead>(res);
}

export async function deleteModel(id: number, apiKey?: string): Promise<void> {
  const res = await fetch(getUrl(`/api/v1/models/${id}`), {
    method: "DELETE",
    headers: writeHeaders(apiKey),
  });
  if (!res.ok) {
    if (res.status === 401) emitUnauthorized();
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
}

// -- Ingestion ------------------------------------------------------------

export async function ingestOrca(
  formData: FormData,
  apiKey?: string,
): Promise<IngestResponse> {
  const res = await fetch(getUrl("/api/v1/ingest/orca"), {
    method: "POST",
    headers: writeHeaders(apiKey),
    body: formData,
  });
  return handleResponse<IngestResponse>(res);
}

export async function getJobStatus(jobId: string): Promise<IngestJobStatus> {
  const res = await fetch(getUrl(`/api/v1/ingest/jobs/${jobId}`), {
    cache: "no-store",
  });
  return handleResponse<IngestJobStatus>(res);
}

export async function ingestModel(
  formData: FormData,
  apiKey?: string,
): Promise<IngestResponse> {
  const res = await fetch(getUrl("/api/v1/ingest/model"), {
    method: "POST",
    headers: writeHeaders(apiKey),
    body: formData,
  });
  return handleResponse<IngestResponse>(res);
}

// -- Taxonomy -------------------------------------------------------------

export async function listCategories(): Promise<CategoryRead[]> {
  const res = await fetch(getUrl("/api/v1/categories"), { cache: "no-store" });
  return handleResponse<CategoryRead[]>(res);
}

export async function createCategory(
  payload: CategoryCreate,
  apiKey?: string,
): Promise<CategoryRead> {
  const res = await fetch(getUrl("/api/v1/categories"), {
    method: "POST",
    headers: jsonHeaders(apiKey),
    body: JSON.stringify(payload),
  });
  return handleResponse<CategoryRead>(res);
}

export async function deleteCategory(id: number, apiKey?: string): Promise<void> {
  const res = await fetch(getUrl(`/api/v1/categories/${id}`), {
    method: "DELETE",
    headers: writeHeaders(apiKey),
  });
  if (!res.ok) {
    if (res.status === 401) emitUnauthorized();
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
}

export async function listTags(): Promise<TagRead[]> {
  const res = await fetch(getUrl("/api/v1/tags"), { cache: "no-store" });
  return handleResponse<TagRead[]>(res);
}

export async function createTag(
  payload: TagCreate,
  apiKey?: string,
): Promise<TagRead> {
  const res = await fetch(getUrl("/api/v1/tags"), {
    method: "POST",
    headers: jsonHeaders(apiKey),
    body: JSON.stringify(payload),
  });
  return handleResponse<TagRead>(res);
}

export async function deleteTag(id: number, apiKey?: string): Promise<void> {
  const res = await fetch(getUrl(`/api/v1/tags/${id}`), {
    method: "DELETE",
    headers: writeHeaders(apiKey),
  });
  if (!res.ok) {
    if (res.status === 401) emitUnauthorized();
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
}

// -- Printers -------------------------------------------------------------

export async function listPrinters(): Promise<PrinterRead[]> {
  const res = await fetch(getUrl("/api/v1/printers"), { cache: "no-store" });
  return handleResponse<PrinterRead[]>(res);
}

export async function getPrinter(id: number): Promise<PrinterRead> {
  const res = await fetch(getUrl(`/api/v1/printers/${id}`), {
    cache: "no-store",
  });
  return handleResponse<PrinterRead>(res);
}

export async function createPrinter(
  payload: PrinterCreate,
  apiKey?: string,
): Promise<PrinterRead> {
  const res = await fetch(getUrl("/api/v1/printers"), {
    method: "POST",
    headers: jsonHeaders(apiKey),
    body: JSON.stringify(payload),
  });
  return handleResponse<PrinterRead>(res);
}

export async function updatePrinter(
  id: number,
  payload: PrinterUpdate,
  apiKey?: string,
): Promise<PrinterRead> {
  const res = await fetch(getUrl(`/api/v1/printers/${id}`), {
    method: "PATCH",
    headers: jsonHeaders(apiKey),
    body: JSON.stringify(payload),
  });
  return handleResponse<PrinterRead>(res);
}

export async function deletePrinter(id: number, apiKey?: string): Promise<void> {
  const res = await fetch(getUrl(`/api/v1/printers/${id}`), {
    method: "DELETE",
    headers: writeHeaders(apiKey),
  });
  if (!res.ok) {
    if (res.status === 401) emitUnauthorized();
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
}

export async function sendToPrinter(
  id: number,
  payload: SendToPrinter,
  apiKey?: string,
): Promise<PrintJobRead> {
  const res = await fetch(getUrl(`/api/v1/printers/${id}/send`), {
    method: "POST",
    headers: jsonHeaders(apiKey),
    body: JSON.stringify(payload),
  });
  return handleResponse<PrintJobRead>(res);
}

async function printerControl(
  id: number,
  action: "pause" | "resume" | "cancel",
  apiKey?: string,
): Promise<void> {
  const res = await fetch(getUrl(`/api/v1/printers/${id}/${action}`), {
    method: "POST",
    headers: writeHeaders(apiKey),
  });
  if (!res.ok) {
    if (res.status === 401) emitUnauthorized();
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
}

export function pausePrinter(id: number, apiKey?: string) {
  return printerControl(id, "pause", apiKey);
}

export function resumePrinter(id: number, apiKey?: string) {
  return printerControl(id, "resume", apiKey);
}

export function cancelPrinter(id: number, apiKey?: string) {
  return printerControl(id, "cancel", apiKey);
}

export async function getPrinterStatus(
  id: number,
): Promise<PrinterStatusResponse> {
  const res = await fetch(getUrl(`/api/v1/printers/${id}/status`), {
    cache: "no-store",
  });
  return handleResponse<PrinterStatusResponse>(res);
}

export async function listPrinterJobs(
  id: number,
  limit = 50,
): Promise<PrintJobRead[]> {
  const res = await fetch(
    getUrl(`/api/v1/printers/${id}/jobs?limit=${limit}`),
    { cache: "no-store" },
  );
  return handleResponse<PrintJobRead[]>(res);
}

export function openPrinterWS(id: number): WebSocket {
  return new WebSocket(getWsUrl(`/api/v1/printers/${id}/ws`));
}

// -- Auth --------------------------------------------------------------------

export async function login(body: LoginRequest): Promise<TokenResponse> {
  const res = await fetch(getUrl("/api/v1/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<TokenResponse>(res);
}

export async function getMe(apiKey?: string): Promise<UserRead> {
  const res = await fetch(getUrl("/api/v1/auth/me"), {
    headers: authHeaders(apiKey),
    cache: "no-store",
  });
  return handleResponse<UserRead>(res);
}
