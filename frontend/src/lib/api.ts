import {
  CategoryRead,
  IngestJobStatus,
  IngestResponse,
  ListModelsParams,
  ModelListItem,
  ModelRead,
  ModelUpdate,
  PrintJobRead,
  PrinterCreate,
  PrinterRead,
  PrinterStatusResponse,
  PrinterUpdate,
  SendToPrinter,
  TagRead,
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
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
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
  apiKey: string,
): Promise<ModelRead> {
  const res = await fetch(getUrl(`/api/v1/models/${id}`), {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<ModelRead>(res);
}

export async function deleteModel(id: number, apiKey: string): Promise<void> {
  const res = await fetch(getUrl(`/api/v1/models/${id}`), {
    method: "DELETE",
    headers: {
      "X-API-Key": apiKey,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
}

// -- Ingestion ------------------------------------------------------------

export async function ingestOrca(
  formData: FormData,
  apiKey: string,
): Promise<IngestResponse> {
  const res = await fetch(getUrl("/api/v1/ingest/orca"), {
    method: "POST",
    headers: {
      "X-API-Key": apiKey,
    },
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
  apiKey: string,
): Promise<IngestResponse> {
  const res = await fetch(getUrl("/api/v1/ingest/model"), {
    method: "POST",
    headers: {
      "X-API-Key": apiKey,
    },
    body: formData,
  });
  return handleResponse<IngestResponse>(res);
}

// -- Taxonomy -------------------------------------------------------------

export async function listCategories(): Promise<CategoryRead[]> {
  const res = await fetch(getUrl("/api/v1/categories"), { cache: "no-store" });
  return handleResponse<CategoryRead[]>(res);
}

export async function listTags(): Promise<TagRead[]> {
  const res = await fetch(getUrl("/api/v1/tags"), { cache: "no-store" });
  return handleResponse<TagRead[]>(res);
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
  apiKey: string,
): Promise<PrinterRead> {
  const res = await fetch(getUrl("/api/v1/printers"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<PrinterRead>(res);
}

export async function updatePrinter(
  id: number,
  payload: PrinterUpdate,
  apiKey: string,
): Promise<PrinterRead> {
  const res = await fetch(getUrl(`/api/v1/printers/${id}`), {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<PrinterRead>(res);
}

export async function deletePrinter(id: number, apiKey: string): Promise<void> {
  const res = await fetch(getUrl(`/api/v1/printers/${id}`), {
    method: "DELETE",
    headers: { "X-API-Key": apiKey },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
}

export async function sendToPrinter(
  id: number,
  payload: SendToPrinter,
  apiKey: string,
): Promise<PrintJobRead> {
  const res = await fetch(getUrl(`/api/v1/printers/${id}/send`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<PrintJobRead>(res);
}

async function printerControl(
  id: number,
  action: "pause" | "resume" | "cancel",
  apiKey: string,
): Promise<void> {
  const res = await fetch(getUrl(`/api/v1/printers/${id}/${action}`), {
    method: "POST",
    headers: { "X-API-Key": apiKey },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
}

export function pausePrinter(id: number, apiKey: string) {
  return printerControl(id, "pause", apiKey);
}

export function resumePrinter(id: number, apiKey: string) {
  return printerControl(id, "resume", apiKey);
}

export function cancelPrinter(id: number, apiKey: string) {
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
