import { getJson, sendJson } from "@/lib/api/request";
import {
  SpoolmanStatus,
  SpoolmanTestResult,
  SpoolmanUpdate,
  SpoolRead,
} from "@/types";

export function getSpoolmanStatus(): Promise<SpoolmanStatus> {
  return getJson<SpoolmanStatus>("/api/v1/spoolman");
}

export function updateSpoolman(body: SpoolmanUpdate): Promise<SpoolmanStatus> {
  return sendJson<SpoolmanStatus>("/api/v1/spoolman", "PUT", body);
}

export function testSpoolman(): Promise<SpoolmanTestResult> {
  return sendJson<SpoolmanTestResult>("/api/v1/spoolman/test", "POST", {});
}

export function listSpools(includeArchived = false): Promise<SpoolRead[]> {
  const q = includeArchived ? "?include_archived=true" : "";
  return getJson<SpoolRead[]>(`/api/v1/spoolman/spools${q}`);
}

export interface SpoolmanSyncResult {
  created: number;
  updated: number;
  adopted: number;
  unlinked: number;
}

export function syncSpoolmanFilaments(): Promise<SpoolmanSyncResult> {
  return sendJson<SpoolmanSyncResult>("/api/v1/spoolman/sync-filaments", "POST", {});
}
