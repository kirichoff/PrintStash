import { useCallback, useEffect, useState } from "react";
import {
  FolderSync,
  Plus,
  RefreshCw,
  Trash2,
  HardDrive,
  AlertTriangle,
} from "lucide-react";
import { ConfirmModal } from "@/components/ui/confirm-modal";
import {
  createExternalLibrary,
  deleteExternalLibrary,
  getJobStatus,
  getVaultConfig,
  listExternalLibraries,
  scanExternalLibrary,
  updateExternalLibrary,
  updateVaultConfig,
} from "@/lib/api";
import { toast } from "@/lib/toast";
import type {
  ExternalLibrary,
  ExternalLibraryCollectionMode,
} from "@/types";

const BTN_PRIMARY =
  "inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded bg-[var(--primary)] text-[var(--primary-foreground)] text-xs font-medium uppercase tracking-wider hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed";
const BTN_SECONDARY =
  "inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded border border-border text-muted-foreground hover:bg-muted transition-colors text-xs font-medium uppercase tracking-wider disabled:opacity-50 disabled:cursor-not-allowed";
const INPUT =
  "w-full px-3 py-2 bg-background border border-border rounded text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent disabled:opacity-50";

function formatDate(value: string | null | undefined): string {
  if (!value) return "Never";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

async function pollScanJob(jobId: string): Promise<void> {
  // Mirrors the upload modal's polling: wait until the scan job terminates.
  const deadline = Date.now() + 15 * 60 * 1000;
  while (Date.now() < deadline) {
    const job = await getJobStatus(jobId);
    if (job.state === "completed") return;
    if (job.state === "failed") {
      throw new Error(job.error || "scan_failed");
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("scan_timeout");
}

export function ExternalLibrariesPanel({ canEdit }: { canEdit: boolean }) {
  const [enabled, setEnabled] = useState(false);
  const [enableBusy, setEnableBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const [libraries, setLibraries] = useState<ExternalLibrary[]>([]);
  const [busyId, setBusyId] = useState<number | "create" | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ExternalLibrary | null>(null);

  // Add-library draft.
  const [name, setName] = useState("");
  const [rootPath, setRootPath] = useState("");
  const [interval, setInterval] = useState(60);
  const [mode, setMode] = useState<ExternalLibraryCollectionMode>("mirror");

  const refresh = useCallback(async () => {
    try {
      setLibraries(await listExternalLibraries());
    } catch (e) {
      toast.error(e);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    getVaultConfig()
      .then((cfg) => {
        if (cancelled) return;
        setEnabled(cfg.external_libraries_enabled);
        setLoaded(true);
        if (cfg.external_libraries_enabled) refresh();
      })
      .catch(() => setLoaded(true));
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  async function toggleFeature(next: boolean) {
    setEnableBusy(true);
    setEnabled(next);
    try {
      await updateVaultConfig({ external_libraries_enabled: next });
      toast.success(next ? "NAS mirroring enabled." : "NAS mirroring disabled.");
      if (next) await refresh();
    } catch (e) {
      setEnabled(!next);
      toast.error(e);
    } finally {
      setEnableBusy(false);
    }
  }

  async function handleCreate() {
    if (!name.trim() || !rootPath.trim()) {
      toast.error("Name and folder path are required.");
      return;
    }
    setBusyId("create");
    try {
      await createExternalLibrary({
        name: name.trim(),
        root_path: rootPath.trim(),
        scan_interval_minutes: Math.max(1, interval),
        collection_mode: mode,
      });
      setName("");
      setRootPath("");
      setInterval(60);
      setMode("mirror");
      toast.success("Library added.");
      await refresh();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusyId(null);
    }
  }

  async function handleScan(lib: ExternalLibrary) {
    setBusyId(lib.id);
    try {
      const resp = await scanExternalLibrary(lib.id);
      await pollScanJob(resp.job_id);
      toast.success(`Scan complete for "${lib.name}".`);
      await refresh();
    } catch (e) {
      toast.error(e);
      await refresh();
    } finally {
      setBusyId(null);
    }
  }

  async function handleToggleEnabled(lib: ExternalLibrary) {
    setBusyId(lib.id);
    try {
      await updateExternalLibrary(lib.id, { enabled: !lib.enabled });
      await refresh();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(lib: ExternalLibrary) {
    setBusyId(lib.id);
    try {
      await deleteExternalLibrary(lib.id);
      toast.success(`Removed "${lib.name}". NAS files were not touched.`);
      await refresh();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusyId(null);
      setDeleteTarget(null);
    }
  }

  if (!loaded) return null;

  return (
    <div className="bg-card border border-border rounded">
      <div className="px-4 sm:px-5 py-3.5 border-b border-border flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div className="w-8 h-8 rounded bg-muted flex items-center justify-center text-muted-foreground flex-shrink-0">
            <FolderSync className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-foreground">
              External libraries (NAS folders)
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Mirror a folder (e.g. on a NAS) in place — files are indexed where they
              live, never copied. Scans reflect adds/removes/edits, and web uploads
              write back into the folder. Off by default.
            </p>
          </div>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          disabled={!canEdit || enableBusy}
          onClick={() => toggleFeature(!enabled)}
          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${
            enabled ? "bg-[var(--primary)]" : "bg-[var(--outline-variant)]"
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              enabled ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
      </div>

      {enabled && (
        <div className="p-4 sm:p-5 space-y-5">
          {/* Existing libraries */}
          {libraries.length === 0 ? (
            <p className="text-[13px] text-muted-foreground">
              No libraries yet. Add a folder below to start mirroring.
            </p>
          ) : (
            <ul className="space-y-3">
              {libraries.map((lib) => {
                const busy = busyId === lib.id;
                const s = lib.last_scan_summary;
                return (
                  <li
                    key={lib.id}
                    className="rounded border border-border bg-background p-3 sm:p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <HardDrive className="h-3.5 w-3.5 text-muted-foreground" />
                          <span className="text-sm font-medium text-foreground truncate">
                            {lib.name}
                          </span>
                          {!lib.enabled && (
                            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70 border border-border rounded px-1.5 py-0.5">
                              paused
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground font-mono mt-1 truncate">
                          {lib.root_path}
                        </p>
                        <p className="text-[11px] text-muted-foreground mt-1">
                          {lib.collection_mode === "mirror"
                            ? "Mirrors subfolders → collections"
                            : "Single collection"}{" "}
                          · every {lib.scan_interval_minutes} min · last scan{" "}
                          {formatDate(lib.last_scanned_at)}
                        </p>
                        {lib.last_scan_status === "error" && (
                          <p className="mt-1 inline-flex items-center gap-1 text-[11px] text-[var(--destructive,#dc2626)]">
                            <AlertTriangle className="h-3 w-3" />
                            {s?.error || "Last scan failed"}
                          </p>
                        )}
                        {lib.last_scan_status === "ok" && s && (
                          <p className="text-[11px] text-muted-foreground mt-1">
                            +{s.added} added · {s.updated} updated · {s.removed} removed
                            {s.errors.length > 0 ? ` · ${s.errors.length} errors` : ""}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-shrink-0 items-center gap-1.5">
                        <button
                          type="button"
                          disabled={!canEdit || busy}
                          onClick={() => handleScan(lib)}
                          className={BTN_SECONDARY}
                        >
                          <RefreshCw
                            className={`h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`}
                          />
                          {busy ? "Scanning" : "Scan now"}
                        </button>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={lib.enabled}
                          aria-label="Auto-scan enabled"
                          disabled={!canEdit || busy}
                          onClick={() => handleToggleEnabled(lib)}
                          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${
                            lib.enabled
                              ? "bg-[var(--primary)]"
                              : "bg-[var(--outline-variant)]"
                          }`}
                        >
                          <span
                            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                              lib.enabled ? "translate-x-6" : "translate-x-1"
                            }`}
                          />
                        </button>
                        <button
                          type="button"
                          disabled={!canEdit || busy}
                          onClick={() => setDeleteTarget(lib)}
                          className="inline-flex h-9 w-9 items-center justify-center rounded border border-border text-muted-foreground hover:bg-muted hover:text-[var(--destructive,#dc2626)] transition-colors disabled:opacity-50"
                          aria-label="Remove library"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          {/* Add a library */}
          <div className="rounded border border-dashed border-border p-3 sm:p-4 space-y-3">
            <p className="text-[11px] font-mono uppercase tracking-wider text-[var(--primary)]">
              Add a folder
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                className={INPUT}
                placeholder="Name (e.g. NAS models)"
                value={name}
                disabled={!canEdit}
                onChange={(e) => setName(e.target.value)}
              />
              <input
                className={INPUT}
                placeholder="Absolute folder path (e.g. /mnt/nas/3d)"
                value={rootPath}
                disabled={!canEdit}
                onChange={(e) => setRootPath(e.target.value)}
              />
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                Scan every
                <input
                  className={`${INPUT} w-20`}
                  type="number"
                  min={1}
                  value={interval}
                  disabled={!canEdit}
                  onChange={(e) => setInterval(Number(e.target.value))}
                />
                min
              </label>
              <select
                className={INPUT}
                value={mode}
                disabled={!canEdit}
                onChange={(e) =>
                  setMode(e.target.value as ExternalLibraryCollectionMode)
                }
              >
                <option value="mirror">Mirror subfolders as collections</option>
                <option value="single">Single collection (flat)</option>
              </select>
            </div>
            <div className="flex justify-end">
              <button
                type="button"
                disabled={!canEdit || busyId === "create"}
                onClick={handleCreate}
                className={BTN_PRIMARY}
              >
                <Plus className="h-3.5 w-3.5" />
                {busyId === "create" ? "Adding" : "Add library"}
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmModal
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Remove external library?"
        description={
          deleteTarget
            ? `"${deleteTarget.name}" will be removed and its indexed models moved to trash. The files on the NAS folder are never touched.`
            : ""
        }
        confirmLabel="Remove"
        busy={deleteTarget !== null && busyId === deleteTarget.id}
        onConfirm={() => deleteTarget && handleDelete(deleteTarget)}
      />
    </div>
  );
}
