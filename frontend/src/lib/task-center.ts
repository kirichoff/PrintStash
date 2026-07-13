"use client";

import { listIngestJobs } from "@/lib/api/models";
import type { IngestJobStatus } from "@/types";

export type TaskStatus = "pending" | "running" | "completed" | "failed";

export interface TaskItem {
  id: string;
  title: string;
  detail?: string;
  status: TaskStatus;
  progress: number;
  createdAt: number;
  updatedAt: number;
  jobId?: string;
  stage?: IngestJobStatus["stage"];
  processed?: number;
  total?: number | null;
  succeeded?: number;
  deduplicated?: number;
  skipped?: number;
  failed?: number;
  completion?: IngestJobStatus["completion"];
  retryable?: boolean;
  failedItems?: Array<{ name: string; reason: string; retryable: boolean }>;
}

const TASK_EVENT = "printstash:tasks-changed";
const STORAGE_KEY = "printstash:import-tasks:v1";
let tasks: TaskItem[] = loadTasks();
let cleanupTimer: ReturnType<typeof setTimeout> | null = null;
let syncTimer: ReturnType<typeof setInterval> | null = null;

function loadTasks(): TaskItem[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.slice(0, 20) : [];
  } catch {
    return [];
  }
}

function persist(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
}

function emit() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(TASK_EVENT));
}

function clampProgress(progress: number): number {
  return Math.max(0, Math.min(100, Math.round(progress)));
}

function taskTtl(task: TaskItem): number | null {
  // Result summaries remain until user explicitly clears them.
  void task;
  return null;
}

function pruneExpired(now = Date.now()): boolean {
  const next = tasks.filter((task) => {
    const ttl = taskTtl(task);
    return ttl === null || now - task.updatedAt < ttl;
  });
  if (next.length === tasks.length) return false;
  tasks = next;
  return true;
}

function scheduleCleanup(): void {
  if (typeof window === "undefined") return;
  if (cleanupTimer) {
    clearTimeout(cleanupTimer);
    cleanupTimer = null;
  }

  const now = Date.now();
  const nextExpiry = tasks.reduce<number | null>((soonest, task) => {
    const ttl = taskTtl(task);
    if (ttl === null) return soonest;
    const expiresAt = task.updatedAt + ttl;
    return soonest === null ? expiresAt : Math.min(soonest, expiresAt);
  }, null);

  if (nextExpiry === null) return;
  cleanupTimer = setTimeout(() => {
    cleanupTimer = null;
    if (pruneExpired()) emit();
    scheduleCleanup();
  }, Math.max(0, nextExpiry - now));
}

export function listTasks(): TaskItem[] {
  if (pruneExpired()) {
    emit();
    scheduleCleanup();
  }
  return [...tasks].sort((a, b) => b.updatedAt - a.updatedAt);
}

export function createTask(
  input: Pick<TaskItem, "title"> &
    Partial<Omit<TaskItem, "id" | "title" | "createdAt" | "updatedAt">>,
): string {
  const now = Date.now();
  const id = `${now}-${Math.random().toString(36).slice(2, 8)}`;
  tasks = [
    {
      id,
      ...input,
      status: input.status ?? "pending",
      progress: clampProgress(input.progress ?? 0),
      createdAt: now,
      updatedAt: now,
    },
    ...tasks,
  ].slice(0, 20);
  persist();
  emit();
  scheduleCleanup();
  return id;
}

export function updateTask(
  id: string,
  patch: Partial<Omit<TaskItem, "id" | "createdAt" | "updatedAt">>,
): void {
  const now = Date.now();
  tasks = tasks.map((task) =>
    task.id === id
      ? {
          ...task,
          ...patch,
          progress:
            patch.progress === undefined
              ? task.progress
              : clampProgress(patch.progress),
          ...(patch.status === "completed" ? { progress: 100 } : {}),
          updatedAt: now,
        }
      : task,
  );
  persist();
  emit();
  scheduleCleanup();
}

export function clearCompletedTasks(): void {
  tasks = tasks.filter(
    (task) => task.status !== "completed" && task.status !== "failed",
  );
  persist();
  emit();
  scheduleCleanup();
}

function detailForJob(job: IngestJobStatus): string {
  const stage = job.stage?.replaceAll("_", " ") ?? job.state;
  const count = job.total == null ? "" : ` ${job.processed ?? 0}/${job.total}`;
  const item = job.current_item ? ` · ${job.current_item}` : "";
  if (job.state === "completed") {
    return `${job.succeeded ?? 0} succeeded, ${job.deduplicated ?? 0} deduplicated, ${job.skipped ?? 0} skipped, ${job.failed ?? 0} failed`;
  }
  if (job.state === "failed") return job.error ?? "Import failed before anything was added";
  return `${stage}${count}${item} · continues in background`;
}

function applyJob(job: IngestJobStatus): void {
  const existing = tasks.find((task) => task.jobId === job.job_id);
  if (existing && existing.status === job.state && (job.state === "completed" || job.state === "failed")) return;
  const status: TaskStatus = job.state;
  const patch = {
    jobId: job.job_id,
    status,
    progress: job.progress ?? (job.total ? ((job.processed ?? 0) / job.total) * 100 : 0),
    detail: detailForJob(job),
    stage: job.stage,
    processed: job.processed,
    total: job.total,
    succeeded: job.succeeded,
    deduplicated: job.deduplicated,
    skipped: job.skipped,
    failed: job.failed,
    completion: job.completion,
    retryable: job.retryable,
    failedItems: job.failed_items,
  };
  if (existing) updateTask(existing.id, patch);
  else createTask({ title: "Import", ...patch });
}

export function trackImportJob(jobId: string, title: string): string {
  const existing = tasks.find((task) => task.jobId === jobId);
  if (existing) return existing.id;
  return createTask({
    title,
    detail: "Queued · continues in background",
    status: "pending",
    progress: 0,
    jobId,
  });
}

export async function syncImportJobs(): Promise<void> {
  const jobs = await listIngestJobs();
  jobs.forEach(applyJob);
}

export function startImportJobSync(): () => void {
  void syncImportJobs().catch(() => undefined);
  if (syncTimer === null && typeof window !== "undefined") {
    syncTimer = setInterval(() => void syncImportJobs().catch(() => undefined), 1_000);
  }
  return () => {};
}

export function subscribeTasks(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(TASK_EVENT, callback);
  return () => window.removeEventListener(TASK_EVENT, callback);
}
