import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createExternalLibrary,
  deleteExternalLibrary,
  listExternalLibraries,
  scanExternalLibrary,
  updateExternalLibrary,
} from "@/lib/api/libraries";
import { getVaultConfig, updateVaultConfig } from "@/lib/api/config";
import { invalidateApiCache } from "@/lib/api/request";

/**
 * Pin the External Libraries (NAS mirroring) API client to the exact wire
 * contract the backend router expects: paths, HTTP verbs, and request bodies.
 * A drift here is a silent break of the whole NAS settings/upload UI.
 */

function jsonResponse(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
    text: async () => JSON.stringify(data),
    headers: new Headers({ "content-type": "application/json" }),
  } as unknown as Response;
}

const fetchMock = vi.fn();

const library = {
  id: 7,
  name: "nas-main",
  root_path: "/mnt/nas/models",
  enabled: true,
  scan_interval_minutes: 60,
  collection_mode: "mirror",
  target_collection_id: null,
  last_scanned_at: null,
  last_scan_status: null,
  last_scan_summary: null,
};

function lastCall() {
  const call = fetchMock.mock.calls.at(-1)!;
  return { url: call[0] as string, init: call[1] as RequestInit };
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
  invalidateApiCache();
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("listExternalLibraries", () => {
  it("GETs the libraries collection and bypasses the cache (fresh)", async () => {
    fetchMock.mockResolvedValue(jsonResponse([library]));

    const result = await listExternalLibraries();

    expect(result).toEqual([library]);
    const { url, init } = lastCall();
    expect(url).toBe("/api/v1/libraries");
    expect(init).toMatchObject({ cache: "no-store" });
  });

  it("re-fetches on every call rather than serving a stale cache", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    await listExternalLibraries();
    await listExternalLibraries();

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("createExternalLibrary", () => {
  it("POSTs the create body and returns the created library", async () => {
    fetchMock.mockResolvedValue(jsonResponse(library));

    const body = {
      name: "nas-main",
      root_path: "/mnt/nas/models",
      scan_interval_minutes: 30,
      collection_mode: "mirror" as const,
    };
    const created = await createExternalLibrary(body);

    expect(created).toEqual(library);
    const { url, init } = lastCall();
    expect(url).toBe("/api/v1/libraries");
    expect(init).toMatchObject({ method: "POST" });
    expect(init.body).toBe(JSON.stringify(body));
  });
});

describe("updateExternalLibrary", () => {
  it("PATCHes the addressed library with a partial body", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ...library, enabled: false }));

    const updated = await updateExternalLibrary(7, { enabled: false });

    expect(updated.enabled).toBe(false);
    const { url, init } = lastCall();
    expect(url).toBe("/api/v1/libraries/7");
    expect(init).toMatchObject({ method: "PATCH" });
    expect(init.body).toBe(JSON.stringify({ enabled: false }));
  });
});

describe("deleteExternalLibrary", () => {
  it("DELETEs the addressed library and resolves void on 204", async () => {
    fetchMock.mockResolvedValue(jsonResponse(null, 204));

    await expect(deleteExternalLibrary(7)).resolves.toBeUndefined();
    const { url, init } = lastCall();
    expect(url).toBe("/api/v1/libraries/7");
    expect(init).toMatchObject({ method: "DELETE" });
  });
});

describe("scanExternalLibrary", () => {
  it("POSTs to the scan endpoint and returns the queued job", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ job_id: "scan-1", state: "pending", message: "library scan queued" }, 202),
    );

    const resp = await scanExternalLibrary(7);

    expect(resp.job_id).toBe("scan-1");
    expect(resp.state).toBe("pending");
    const { url, init } = lastCall();
    expect(url).toBe("/api/v1/libraries/7/scan");
    expect(init).toMatchObject({ method: "POST" });
  });
});

describe("vault config — external libraries flag", () => {
  it("reads external_libraries_enabled from GET /api/v1/config", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ storage_backend: "local", external_libraries_enabled: true }),
    );

    const cfg = await getVaultConfig();

    expect(cfg.external_libraries_enabled).toBe(true);
    expect(lastCall().url).toBe("/api/v1/config");
  });

  it("PUTs a toggle of external_libraries_enabled", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ storage_backend: "local", external_libraries_enabled: false }),
    );

    const cfg = await updateVaultConfig({ external_libraries_enabled: false });

    expect(cfg.external_libraries_enabled).toBe(false);
    const { url, init } = lastCall();
    expect(url).toBe("/api/v1/config");
    expect(init).toMatchObject({ method: "PUT" });
    expect(init.body).toBe(JSON.stringify({ external_libraries_enabled: false }));
  });
});
